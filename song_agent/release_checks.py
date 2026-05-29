from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import hashlib
import base64
import struct
import threading
import time
import wave
import zipfile
from http.client import HTTPConnection
from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.agent.pipeline import deterministic_compose
from song_agent.assets import AssetStore, apply_asset_refs_to_plan, extract_assets_from_song_plan, write_asset_refs_snapshot
from song_agent import candidate_groups as candidate_groups_module
from song_agent.candidate_groups import CandidateGroupStore, candidate_audio_path, candidate_group_stale, candidate_midi_path
from song_agent.candidate_scoring import score_provider_edit_candidate
from song_agent.edits import EditIntent, apply_edit_intent, build_edit_metadata
from song_agent.edit_presets import EditPresetStore, merge_preset_intent
from song_agent.editor_templates import EditorTemplateStore
from song_agent.editor_view import build_editor_diff, build_editor_view, build_editor_view_from_result
from song_agent.final_export import FinalExportOptions, build_final_export_bundle, build_final_export_zip
from song_agent.context_packs import ContextPackStore, context_pack_snapshot, write_context_pack_snapshot
from song_agent.library_index import LibraryIndexStore, recommend_library_context, search_library
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.provider_usage import build_provider_usage_report, collect_project_provider_usage_records
from song_agent.prompt_ab import PromptABStore
from song_agent.project_compare import compare_project_versions
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore
from song_agent.provider import ProviderConfig
from song_agent.provider_edits import (
    ProviderEditPatch,
    create_provider_edit_preview,
    generate_provider_edit_candidates,
    generate_provider_edit_patch,
    apply_provider_edit_patch,
    mark_provider_edit_preview_applied,
    preview_stale,
    song_plan_hash,
)
from song_agent.references import ReferenceStore, reference_refs_snapshot, write_reference_refs_snapshot
from song_agent.reference_analysis import analyze_reference, create_asset_from_slice, generate_slices, render_reference_slice_midi
from song_agent.renderers.audio import RendererConfig
from song_agent.renderers.midi import render_midi
from song_agent.release_verifier import verify_release_zip
from song_agent.audio_revision import CANDIDATE_INTEGRITY_EXCLUDE, _object_hash as _audio_revision_object_hash
from song_agent.audio_artifacts import build_audio_artifact_manifest, write_audio_artifact_manifest
from song_agent.distribution_verifier import verify_distribution_package
from song_agent.submission_verifier import verify_submission_package
from song_agent.human_review_verifier import verify_human_review_pack
from song_agent.music_acceptance import AcceptanceStore
from song_agent.releases import stable_hash
from song_agent.schemas.song import SongRequest
from song_agent.song_editor import EditorPreviewStore, apply_editor_patch, build_editor_state, editor_edit_metadata


SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"x-access-token",
        r"Authorization:\s*Bearer\s+\S+",
        r"sk-[A-Za-z0-9_-]{16,}",
        r"api_key\s*[:=]\s*['\"][^'\"]{8,}",
        r"access_token\s*[:=]\s*['\"][^'\"]{8,}",
        r"C:\\Users\\[^\\]+\\Documents\\projects\\githubkey\.txt",
    )
]
SECRET_SCAN_PATHS = [
    "README.md",
    "CHANGELOG.md",
    "material",
    "song_agent",
    "tests",
    "pyproject.toml",
    ".gitignore",
]
ALLOWED_SECRET_FIXTURE_PATTERNS = [
    "tests/test_provider_client.py",
    "tests\\test_provider_client.py",
    "material/",
    "material\\",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ReleaseCheckReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(CheckResult(name=name, ok=ok, detail=detail))


def run_release_checks(*, run_tests: bool = True, repo_root: Path | None = None) -> ReleaseCheckReport:
    root = repo_root or Path.cwd()
    report = ReleaseCheckReport()
    if run_tests:
        tests = _run(["python", "-m", "pytest", "-q"], root)
        report.add("pytest", tests.returncode == 0, _last_lines(tests.stdout + tests.stderr))
    diff = _run(["git", "diff", "--check"], root)
    report.add("git diff --check", diff.returncode == 0, _last_lines(diff.stdout + diff.stderr))
    status = _run(["git", "status", "--short", "--branch"], root)
    status_text = status.stdout.strip()
    report.add(
        "git status",
        status.returncode == 0 and _status_is_clean(status_text),
        status_text,
    )
    remotes = _run(["git", "remote", "-v"], root)
    report.add(
        "remote url token check",
        remotes.returncode == 0 and not _remote_has_token(remotes.stdout),
        _redact_remote(remotes.stdout.strip()),
    )
    tracked = _run(
        [
            "git",
            "ls-files",
            ".musicforge/provider.json",
            ".musicforge/renderer.json",
            ".musicforge/edit-presets.json",
            ".musicforge/prompt-templates.json",
            ".musicforge/references/ref-001/reference.json",
        ],
        root,
    )
    report.add(
        ".musicforge configs untracked",
        tracked.returncode == 0 and not tracked.stdout.strip(),
        tracked.stdout.strip(),
    )
    ignored = _run(
        [
            "git",
            "check-ignore",
            "-v",
            ".musicforge/provider.json",
            ".musicforge/renderer.json",
            ".musicforge/edit-presets.json",
            ".musicforge/prompt-templates.json",
            ".musicforge/references/ref-001/reference.json",
        ],
        root,
    )
    report.add(
        ".musicforge configs ignored",
        ignored.returncode == 0,
        ignored.stdout.strip(),
    )
    report.add("version consistency", *_version_consistency(root))
    report.add("secret scan", *_secret_scan(root))
    report.add("final export smoke", *_final_export_smoke(root))
    report.add("edit smoke", *_edit_smoke(root))
    report.add("v1.2 workflow smoke", *_v12_workflow_smoke(root))
    report.add("v1.2.1 hardening smoke", *_v121_hardening_smoke(root))
    report.add("v1.3 provider edit smoke", *_v13_provider_edit_smoke(root))
    report.add("v1.4 candidate edit smoke", *_v14_candidate_edit_smoke(root))
    report.add("v1.5 candidate audition and usage smoke", *_v15_candidate_audition_usage_smoke(root))
    report.add("v1.6 creative assets smoke", *_v16_creative_assets_smoke(root))
    report.add("v1.7 reference library smoke", *_v17_reference_library_smoke(root))
    report.add("v1.8 reference analysis smoke", *_v18_reference_analysis_smoke(root))
    report.add("v1.9 library context smoke", *_v19_library_context_smoke(root))
    report.add("v2.0 visual editor smoke", *_v20_visual_editor_smoke(root))
    report.add("v2.1 structure editor smoke", *_v21_structure_editor_smoke(root))
    report.add("v2.2 interactive editor smoke", *_v22_interactive_editor_smoke(root))
    report.add("v2.3 editor clip insert smoke", *_v23_editor_clip_insert_smoke(root))
    report.add("v2.4 editor template smoke", *_v24_editor_template_smoke(root))
    report.add("v2.5 editor audition smoke", *_v25_editor_audition_smoke(root))
    report.add("v2.6 audition review smoke", *_v26_audition_review_smoke(root))
    report.add("v2.7 review edit smoke", *_v27_review_edit_smoke(root))
    report.add("v2.8 review task smoke", *_v28_review_task_smoke(root))
    report.add("v2.9 provider review candidates smoke", *_v29_provider_review_candidates_smoke(root))
    report.add("v3.0 review sprint smoke", *_v30_review_sprint_smoke(root))
    report.add("v3.1 review sprint recommendations smoke", *_v31_review_sprint_recommendations_smoke(root))
    report.add("v3.2 review sprint action queue smoke", *_v32_review_sprint_action_queue_smoke(root))
    report.add("v3.3 review sprint dashboard metrics smoke", *_v33_review_sprint_dashboard_metrics_smoke(root))
    report.add("v3.4 provider review judge smoke", *_v34_provider_review_judge_smoke(root))
    report.add("v3.5 review sprint closeout smoke", *_v35_review_sprint_closeout_smoke(root))
    report.add("v3.6 delivery qa handoff smoke", *_v36_delivery_qa_handoff_smoke(root))
    report.add("v3.7 release workspace smoke", *_v37_release_workspace_smoke(root))
    report.add("v3.8 release zip verifier smoke", *_v38_release_zip_verifier_smoke(root))
    report.add("v3.9 release metadata smoke", *_v39_release_metadata_smoke(root))
    report.add("v4.0 distribution prep smoke", *_v40_distribution_prep_smoke(root))
    report.add("v4.1 distribution template packs smoke", *_v41_distribution_template_packs_smoke(root))
    report.add("v4.2 distribution layout contract smoke", *_v42_distribution_layout_contract_smoke(root))
    report.add("v4.3 submission workspace smoke", *_v43_submission_workspace_smoke(root))
    report.add("v4.4 music acceptance lab smoke", *_v44_music_acceptance_lab_smoke(root))
    report.add("v4.5 acceptance profiles songbook smoke", *_v45_acceptance_profiles_songbook_smoke(root))
    report.add("v4.6 human review pack smoke", *_v46_human_review_pack_smoke(root))
    report.add("v4.7 acceptance analytics smoke", *_v47_acceptance_analytics_smoke(root))
    report.add("v4.8 acceptance fix sprint smoke", *_v48_acceptance_fix_sprint_smoke(root))
    report.add("v4.9 acceptance knowledge base smoke", *_v49_acceptance_knowledge_base_smoke(root))
    report.add("v4.10 knowledge-assisted fix planning smoke", *_v410_knowledge_assisted_fix_planning_smoke(root))
    report.add("v4.11 fix plan outcome review smoke", *_v411_fix_plan_outcome_review_smoke(root))
    report.add("v4.12 planning rule simulation smoke", *_v412_planning_rule_simulation_smoke(root))
    report.add("v4.13 planning rule governance smoke", *_v413_planning_rule_governance_smoke(root))
    report.add("v4.14 planning rule impact smoke", *_v414_planning_rule_impact_smoke(root))
    report.add("v5.0 real audio baseline smoke", *_v50_real_audio_baseline_smoke(root))
    report.add("v5.1 per-track audio review smoke", *_v51_per_track_audio_review_smoke(root))
    report.add("v5.2 arrangement mix controls smoke", *_v52_arrangement_mix_controls_smoke(root))
    report.add("v5.3 audio revision workbench smoke", *_v53_audio_revision_workbench_smoke(root))
    report.add("v5.4 mastering qa smoke", *_v54_mastering_qa_smoke(root))
    return report


def print_release_check_report(report: ReleaseCheckReport) -> None:
    print("MusicForge release-check")
    for result in report.results:
        status = "ok" if result.ok else "failed"
        print(f"{result.name}: {status}")
        if result.detail:
            for line in result.detail.splitlines():
                print(f"  {line}")


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        shell=False,
        encoding="utf-8",
        errors="replace",
    )


def _status_is_clean(status_text: str) -> bool:
    lines = [line for line in status_text.splitlines() if line.strip()]
    if not lines:
        return True
    if len(lines) == 1 and lines[0].startswith("## "):
        return "[ahead" not in lines[0] and "[behind" not in lines[0]
    return False


def _remote_has_token(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("x-access-token", "ghp_", "github_pat_"))


def _redact_remote(value: str) -> str:
    value = re.sub(r"https://[^@\s]+@", "https://***@", value)
    value = re.sub(r"(x-access-token:)[^@\s]+", r"\1***", value, flags=re.IGNORECASE)
    return value


def _version_consistency(root: Path) -> tuple[bool, str]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    package_version = __version__
    pyproject_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    pyproject_version = pyproject_match.group(1) if pyproject_match else ""
    ok = bool(pyproject_version == package_version and f"## v{package_version}" in changelog)
    return ok, f"package={package_version}, pyproject={pyproject_version}"


def _secret_scan(root: Path) -> tuple[bool, str]:
    matches: list[str] = []
    for scan_path in SECRET_SCAN_PATHS:
        path = root / scan_path
        if path.is_dir():
            files = [file for file in path.rglob("*") if file.is_file()]
        elif path.exists():
            files = [path]
        else:
            continue
        for file in files:
            if _skip_file(file):
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = str(file.relative_to(root))
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                    hit = f"{relative}:{line_number}: {_redact_line(line.strip())}"
                    if _is_allowed_fixture_hit(relative, line):
                        continue
                    matches.append(hit)
    if matches:
        return False, "\n".join(matches[:20])
    return True, "no disallowed secret patterns found"


def _final_export_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-release-") as temp_dir:
            base = Path(temp_dir)
            run_dir = base / "runs" / "release-smoke"
            project_dir = base / ".musicforge" / "projects" / "release-smoke"
            request = SongRequest(
                title="Release Smoke",
                language="en",
                style="synth pop",
                theme="release check",
                tempo_bpm=96,
            )
            plan = deterministic_compose(request)
            plan_path = run_dir / "data" / "song-plan.json"
            midi_path = run_dir / "renders" / "song.mid"
            write_json(plan_path, plan.to_dict())
            write_json(run_dir / "data" / "run-summary.json", {"title": plan.title})
            write_json(run_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(plan, midi_path)
            gate = evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-06T00:00:00+00:00")
            manifest = build_final_export_bundle(
                project=_SmokeProject(),
                version=_SmokeVersion(run_dir),
                project_dir=project_dir,
                run_dir=run_dir,
                gate=gate,
                options=FinalExportOptions(),
                now="2026-05-06T00:00:00+00:00",
                project_export={"project": {"project_id": "release-smoke"}},
            )
            required = [
                project_dir / "final-export" / "manifest.json",
                project_dir / "final-export" / "song-plan.json",
                project_dir / "final-export" / "song.mid",
                project_dir / "final-export" / "quality-report.json",
            ]
            ok = gate.status in {"passed", "warning"} and all(path.exists() for path in required)
            return ok, f"version={manifest.get('version_id')}, gate={gate.status}"
    except Exception as exc:
        return False, str(exc)


def _edit_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-edit-") as temp_dir:
            base = Path(temp_dir)
            parent_dir = base / "runs" / "edit-parent"
            child_dir = base / "runs" / "edit-child"
            request = SongRequest(
                title="Edit Smoke",
                language="en",
                style="synth pop",
                theme="release edit check",
                tempo_bpm=96,
            )
            parent_plan = deterministic_compose(request)
            parent_plan_path = parent_dir / "data" / "song-plan.json"
            write_json(parent_plan_path, parent_plan.to_dict())
            parent_hash = _file_sha256(parent_plan_path)
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": "chorus"},
                    "strength": 7,
                    "preserve": ["tempo", "key", "structure"],
                }
            )
            result = apply_edit_intent(parent_plan, intent)
            child_plan_path = child_dir / "data" / "song-plan.json"
            child_midi_path = child_dir / "renders" / "song.mid"
            metadata_path = child_dir / "data" / "edit-metadata.json"
            write_json(child_plan_path, result.plan.to_dict())
            render_midi(result.plan, child_midi_path)
            write_json(
                metadata_path,
                build_edit_metadata(
                    project_id="release-edit",
                    parent_version_id="v001",
                    parent_job_id="edit-parent",
                    intent=intent,
                    created_at="2026-05-06T00:00:00+00:00",
                    summary=result.summary,
                    warnings=result.warnings,
                ),
            )
            parent_unchanged = _file_sha256(parent_plan_path) == parent_hash
            ok = parent_unchanged and child_midi_path.exists() and metadata_path.exists()
            return ok, f"parent_unchanged={parent_unchanged}, midi={child_midi_path.exists()}"
    except Exception as exc:
        return False, str(exc)


def _v12_workflow_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v12-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            presets = EditPresetStore(base / ".musicforge" / "edit-presets.json")
            document = store.create_project("Release v1.2 Smoke")
            request = SongRequest(
                title="Release v1.2 Smoke",
                language="en",
                style="synth pop",
                theme="release check",
                tempo_bpm=96,
            )
            parent_dir = base / "runs" / "v12-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            parent_job = _SmokeJob("v12-parent", parent_dir, request.to_dict())
            document = store.add_version_from_job(document.state.project_id, parent_job, name="Parent")

            preset = presets.get_preset("brighter-chorus-harmony")
            intent_payload = merge_preset_intent(preset, {"name": "Preset Child"}, parent_plan)
            intent = EditIntent.from_dict(intent_payload)
            result = apply_edit_intent(parent_plan, intent)
            child_dir = base / "runs" / "v12-child"
            write_json(child_dir / "data" / "song-plan.json", result.plan.to_dict())
            render_midi(result.plan, child_dir / "renders" / "song.mid")
            write_json(
                child_dir / "data" / "edit-metadata.json",
                build_edit_metadata(
                    project_id=document.state.project_id,
                    parent_version_id="v001",
                    parent_job_id="v12-parent",
                    intent=intent,
                    created_at="2026-05-06T00:00:00+00:00",
                    summary=result.summary,
                    warnings=result.warnings,
                )
                | {"preset": preset.public_ref()},
            )
            child_job = _SmokeJob("v12-child", child_dir, request.to_dict())
            document = store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Preset Child",
                parent_version_id="v001",
                variant_type="section_edit",
                change_summary="preset harmony",
            )
            compare = compare_project_versions(document, "v001", "v002")
            gate = evaluate_quality_gate(child_dir, QualityGateConfig(), now="2026-05-06T00:00:00+00:00")
            project_dir = store.project_dir(document.state.project_id)
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=project_dir,
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v002"),
                now="2026-05-06T00:00:00+00:00",
                project_export=store.export_project(document.state.project_id),
            )
            zip_info = build_final_export_zip(project_dir, now="2026-05-06T00:00:00+00:00")
            safe_entries = all(not entry.startswith(("/", "\\")) and ".." not in entry.split("/") for entry in zip_info["entries"])
            ok = (
                compare["right"]["edit"]["preset_id"] == "brighter-chorus-harmony"
                and manifest["version_id"] == "v002"
                and zip_info["entry_count"] >= 4
                and safe_entries
            )
            return ok, f"preset={preset.preset_id}, compare={compare['summary']['recommendation']}, zip_entries={zip_info['entry_count']}"
    except Exception as exc:
        return False, str(exc)


def _v121_hardening_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v121-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            document = store.create_project("Release v1.2.1 Smoke")
            request = SongRequest(
                title="Release v1.2.1 Smoke",
                language="en",
                style="synth pop",
                theme="release check",
                tempo_bpm=96,
            )
            run_dir = base / "runs" / "v121-parent"
            plan = deterministic_compose(request)
            write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
            write_json(run_dir / "data" / "run-summary.json", {"title": plan.title})
            write_json(run_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(plan, run_dir / "renders" / "song.mid")
            document = store.add_version_from_job(
                document.state.project_id,
                _SmokeJob("v121-parent", run_dir, request.to_dict()),
                name="Parent",
            )
            project_dir = store.project_dir(document.state.project_id)
            gate = evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-07T00:00:00+00:00")
            build_final_export_bundle(
                project=document.state,
                version=document.versions[0],
                project_dir=project_dir,
                run_dir=run_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v001"),
                now="2026-05-07T00:00:00+00:00",
                project_export=store.export_project(document.state.project_id),
            )
            build_final_export_zip(project_dir, now="2026-05-07T00:00:00+00:00")
            zip_exists_before = (project_dir / "final-export.zip").exists()
            build_final_export_bundle(
                project=document.state,
                version=document.versions[0],
                project_dir=project_dir,
                run_dir=run_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v001"),
                now="2026-05-07T01:00:00+00:00",
                project_export=store.export_project(document.state.project_id),
            )
            zip_cleared = not (project_dir / "final-export.zip").exists()
            try:
                compare_project_versions(document, "", "v001")
            except ValueError as exc:
                compare_guard = "left and right version ids are required" in str(exc)
            else:
                compare_guard = False
            ok = zip_exists_before and zip_cleared and compare_guard
            return ok, f"zip_cleared={zip_cleared}, compare_guard={compare_guard}"
    except Exception as exc:
        return False, str(exc)


def _v13_provider_edit_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v13-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            templates = PromptTemplateStore(base / ".musicforge" / "prompt-templates.json")
            document = store.create_project("Release v1.3 Smoke")
            request = SongRequest(
                title="Release v1.3 Smoke",
                language="en",
                style="synth pop",
                theme="provider edit smoke",
                tempo_bpm=96,
            )
            parent_dir = base / "runs" / "v13-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            parent_job = _SmokeJob("v13-parent", parent_dir, request.to_dict())
            document = store.add_version_from_job(document.state.project_id, parent_job, name="Parent")
            template = templates.get_template("provider-edit-intent")
            patch, snapshot = generate_provider_edit_patch(
                parent_plan=parent_plan,
                instruction="Make the final chorus more energetic but keep lyrics.",
                template=template,
                config=ProviderConfig(wire_api="mock", model="mock-main", api_key="sk-release-secret"),
            )
            snapshot["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            snapshot["request_id"] = "req-release-smoke"
            preview = create_provider_edit_preview(
                project_dir=store.project_dir(document.state.project_id),
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v13-parent",
                parent_plan=parent_plan,
                instruction="Make the final chorus more energetic but keep lyrics.",
                template=template,
                patch=patch,
                now="2026-05-07T00:00:00+00:00",
                provider_usage=snapshot["usage"],
                provider_request_id=snapshot["request_id"],
            )
            stale_plan = deterministic_compose(SongRequest(title="Different Parent", language="en", style="pop", theme="changed"))
            stale_guard = preview_stale(preview, stale_plan)
            result = apply_provider_edit_patch(parent_plan, patch)
            child_dir = base / "runs" / "v13-child"
            write_json(child_dir / "data" / "song-plan.json", result.plan.to_dict())
            write_json(
                child_dir / "data" / "edit-metadata.json",
                build_edit_metadata(
                    project_id=document.state.project_id,
                    parent_version_id="v001",
                    parent_job_id="v13-parent",
                    intent=EditIntent.from_dict(
                        {
                            "edit_type": "section_energy",
                            "target": {"section_name": "chorus"},
                            "provider_mode": "provider",
                        }
                    ),
                    created_at="2026-05-07T00:00:00+00:00",
                    summary=result.summary,
                    warnings=result.warnings,
                )
                | {
                    "provider_mode": "provider",
                    "provider_patch": patch.to_dict(),
                    "provider": snapshot,
                    "template_id": template.template_id,
                },
            )
            write_json(
                child_dir / "data" / "provider-usage.json",
                {
                    "provider_type": "mock",
                    "model": "mock-main",
                    "operation": "provider_edit_apply",
                    "template_id": template.template_id,
                    "prompt_tokens": preview.provider_usage["prompt_tokens"],
                    "completion_tokens": preview.provider_usage["completion_tokens"],
                    "total_tokens": preview.provider_usage["total_tokens"],
                    "request_id": preview.provider_request_id,
                },
            )
            render_midi(result.plan, child_dir / "renders" / "song.mid")
            child_job = _SmokeJob("v13-child", child_dir, request.to_dict())
            child_job.generation_mode = "provider"
            child_job.artifacts["provider_usage"] = str(child_dir / "data" / "provider-usage.json")
            document = store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Provider Edit",
                parent_version_id="v001",
                variant_type="provider_edit",
                change_summary=patch.summary,
            )
            applied_preview = mark_provider_edit_preview_applied(
                store.project_dir(document.state.project_id),
                preview.preview_id,
                "v13-child",
                "v002",
            )
            compare = compare_project_versions(document, "v001", "v002")
            serialized = str(compare) + str(snapshot)
            ok = (
                compare["right"]["edit"]["provider_mode"] == "provider"
                and compare["right"]["edit"]["provider_patch"]["operation_count"] >= 1
                and stale_guard
                and applied_preview.status == "applied"
                and preview.provider_usage["total_tokens"] == 15
                and "sk-release-secret" not in serialized
            )
            return ok, f"template={template.template_id}, operations={len(patch.operations)}, usage={preview.provider_usage['total_tokens']}, stale_guard={stale_guard}, compare={compare['summary']['recommendation']}"
    except Exception as exc:
        return False, str(exc)


def _v14_candidate_edit_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v14-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            templates = PromptTemplateStore(base / ".musicforge" / "prompt-templates.json")
            document = store.create_project("Release v1.4 Smoke")
            request = SongRequest(
                title="Release v1.4 Smoke",
                language="en",
                style="synth pop",
                theme="candidate edit smoke",
                tempo_bpm=98,
            )
            parent_dir = base / "runs" / "v14-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            parent_job = _SmokeJob("v14-parent", parent_dir, request.to_dict())
            document = store.add_version_from_job(document.state.project_id, parent_job, name="Parent")
            template = templates.get_template("provider-edit-candidates")
            patches, snapshot = generate_provider_edit_candidates(
                parent_plan=parent_plan,
                instruction="Give me three stronger chorus options.",
                template=template,
                config=ProviderConfig(wire_api="mock", model="mock-main", api_key="sk-release-secret"),
                candidate_count=3,
            )
            snapshot["usage"] = {"prompt_tokens": 20, "completion_tokens": 9, "total_tokens": 29}
            snapshot["request_id"] = "req-candidate-smoke"
            project_dir = store.project_dir(document.state.project_id)
            group_store = CandidateGroupStore(project_dir)
            group = group_store.create_group(
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v14-parent",
                instruction="Give me three stronger chorus options.",
                template_id=template.template_id,
                candidate_count=3,
                source={"parent_version_id": "v001", "parent_job_id": "v14-parent", "song_plan_sha256": song_plan_hash(parent_plan)},
                provider_usage=snapshot["usage"],
                provider_request_id=snapshot["request_id"],
                now="2026-05-07T00:00:00+00:00",
            )
            write_json(
                project_dir / "candidate-groups" / group.group_id / "provider-usage.json",
                {
                    "provider_type": "mock",
                    "model": "mock-main",
                    "operation": "provider_edit_candidates",
                    "template_id": template.template_id,
                    "prompt_tokens": snapshot["usage"]["prompt_tokens"],
                    "completion_tokens": snapshot["usage"]["completion_tokens"],
                    "total_tokens": snapshot["usage"]["total_tokens"],
                    "request_id": snapshot["request_id"],
                },
            )
            for patch in patches:
                result = apply_provider_edit_patch(parent_plan, patch)
                scores = score_provider_edit_candidate(parent_plan=parent_plan, candidate_plan=result.plan, patch=patch)
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="ready",
                    patch=patch.to_dict(),
                    scores=scores.to_dict(),
                    validator={"status": "passed"},
                    quality=result.plan.quality.to_dict() if result.plan.quality else None,
                    candidate_plan=result.plan.to_dict(),
                    now="2026-05-07T00:00:00+00:00",
                )
            group = group_store.read_group(group.group_id)
            candidate_id = str(group.ranking[0]["candidate_id"])
            selected_candidate = next(candidate for candidate in group.candidates if candidate.candidate_id == candidate_id)
            selected_patch = ProviderEditPatch.from_dict(group_store.read_candidate_patch(group.group_id, candidate_id))
            result = apply_provider_edit_patch(parent_plan, selected_patch)
            child_dir = base / "runs" / "v14-child"
            candidate_summary = {
                "candidate_group_id": group.group_id,
                "candidate_id": candidate_id,
                "rank": selected_candidate.rank,
                "score": selected_candidate.scores.get("combined"),
                "quality_overall": selected_candidate.scores.get("quality_overall"),
                "summary": selected_candidate.summary,
                "status": selected_candidate.status,
                "created_at": selected_candidate.created_at,
            }
            write_json(child_dir / "data" / "song-plan.json", result.plan.to_dict())
            write_json(
                child_dir / "data" / "edit-metadata.json",
                build_edit_metadata(
                    project_id=document.state.project_id,
                    parent_version_id="v001",
                    parent_job_id="v14-parent",
                    intent=EditIntent.from_dict(
                        {
                            "edit_type": "section_energy",
                            "target": {"section_name": "chorus"},
                            "provider_mode": "provider",
                        }
                    ),
                    created_at="2026-05-07T00:00:00+00:00",
                    summary=result.summary,
                    warnings=result.warnings,
                )
                | {
                    "provider_mode": "provider",
                    "provider_patch": selected_patch.to_dict(),
                    "provider": snapshot,
                    "template_id": template.template_id,
                    "candidate_group_id": group.group_id,
                    "candidate_id": candidate_id,
                    "candidate": candidate_summary,
                },
            )
            write_json(
                child_dir / "data" / "provider-usage.json",
                {
                    "provider_type": "mock",
                    "model": "mock-main",
                    "operation": "provider_edit_candidate_apply",
                    "template_id": template.template_id,
                    "total_tokens": group.provider_usage["total_tokens"],
                    "request_id": group.provider_request_id,
                },
            )
            render_midi(result.plan, child_dir / "renders" / "song.mid")
            child_job = _SmokeJob("v14-child", child_dir, request.to_dict())
            child_job.generation_mode = "provider"
            child_job.artifacts["provider_usage"] = str(child_dir / "data" / "provider-usage.json")
            document = store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Provider Candidate",
                parent_version_id="v001",
                variant_type="provider_edit",
                change_summary=selected_patch.summary,
            )
            applied_group = group_store.mark_applied(group.group_id, candidate_id, version_id="v002", job_id="v14-child")
            group_store.delete_group(group.group_id)
            child_metadata_after_delete = read_json(child_dir / "data" / "edit-metadata.json")
            stale_plan = deterministic_compose(SongRequest(title="Different Candidate Parent", language="en", style="pop", theme="changed"))
            stale_guard = candidate_group_stale(group, song_plan_hash(stale_plan))
            compare = compare_project_versions(document, "v001", "v002")
            serialized = str(group.to_dict()) + str(compare) + str(snapshot) + str(child_metadata_after_delete)
            ok = (
                len(group.candidates) == 3
                and len(group.ranking) == 3
                and applied_group.status == "applied"
                and applied_group.selected_candidate_id == candidate_id
                and child_metadata_after_delete.get("candidate_group_id") == group.group_id
                and child_metadata_after_delete.get("candidate_id") == candidate_id
                and (child_metadata_after_delete.get("candidate") or {}).get("rank") is not None
                and (child_metadata_after_delete.get("candidate") or {}).get("score") is not None
                and stale_guard
                and compare["right"]["edit"]["provider_mode"] == "provider"
                and "sk-release-secret" not in serialized
            )
            return ok, f"group={group.group_id}, candidates={len(group.candidates)}, selected={candidate_id}, rank={(child_metadata_after_delete.get('candidate') or {}).get('rank')}, usage={group.provider_usage['total_tokens']}, stale_guard={stale_guard}"
    except Exception as exc:
        return False, str(exc)


def _v15_candidate_audition_usage_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v15-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            templates = PromptTemplateStore(base / ".musicforge" / "prompt-templates.json")
            document = store.create_project("Release v1.5 Smoke")
            request = SongRequest(
                title="Release v1.5 Smoke",
                language="en",
                style="synth pop",
                theme="candidate audition smoke",
                tempo_bpm=100,
            )
            parent_dir = base / "runs" / "v15-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            parent_job = _SmokeJob("v15-parent", parent_dir, request.to_dict())
            document = store.add_version_from_job(document.state.project_id, parent_job, name="Parent")
            project_id = document.state.project_id
            project_dir = store.project_dir(project_id)
            template = templates.get_template("provider-edit-candidates")
            group_store = CandidateGroupStore(project_dir)
            created_groups = []
            for label in ("A", "B"):
                patches, snapshot = generate_provider_edit_candidates(
                    parent_plan=parent_plan,
                    instruction=f"Give me two stronger chorus options {label}.",
                    template=template,
                    config=ProviderConfig(wire_api="mock", model="mock-main", api_key="sk-release-secret"),
                    candidate_count=2,
                )
                snapshot["usage"] = {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}
                snapshot["request_id"] = f"req-v15-{label.lower()}"
                group = group_store.create_group(
                    project_id=project_id,
                    parent_version_id="v001",
                    parent_job_id="v15-parent",
                    instruction=f"Give me two stronger chorus options {label}.",
                    template_id=template.template_id,
                    candidate_count=2,
                    source={"parent_version_id": "v001", "parent_job_id": "v15-parent", "song_plan_sha256": song_plan_hash(parent_plan)},
                    provider_usage=snapshot["usage"],
                    provider_request_id=snapshot["request_id"],
                    now="2026-05-07T00:00:00+00:00",
                )
                write_json(
                    project_dir / "candidate-groups" / group.group_id / "provider-usage.json",
                    {
                        "provider_type": "mock",
                        "model": "mock-main",
                        "operation": "provider_edit_candidates",
                        "template_id": template.template_id,
                        "prompt_tokens": snapshot["usage"]["prompt_tokens"],
                        "completion_tokens": snapshot["usage"]["completion_tokens"],
                        "total_tokens": snapshot["usage"]["total_tokens"],
                        "request_id": snapshot["request_id"],
                    },
                )
                for patch in patches:
                    result = apply_provider_edit_patch(parent_plan, patch)
                    scores = score_provider_edit_candidate(parent_plan=parent_plan, candidate_plan=result.plan, patch=patch)
                    candidate = group_store.add_candidate(
                        group,
                        summary=patch.summary,
                        status="ready",
                        patch=patch.to_dict(),
                        scores=scores.to_dict(),
                        validator={"status": "passed"},
                        quality=result.plan.quality.to_dict() if result.plan.quality else None,
                        candidate_plan=result.plan.to_dict(),
                        now="2026-05-07T00:00:00+00:00",
                    )
                    group_store.render_candidate_midi(group.group_id, candidate.candidate_id)
                created_groups.append(group_store.read_group(group.group_id))
            ab = PromptABStore(project_dir).create_experiment(
                project_id=project_id,
                parent_version_id="v001",
                instruction="Compare prompt candidates.",
                candidate_count=2,
                template_ids=[template.template_id, template.template_id],
                group_ids=[group.group_id for group in created_groups],
                now="2026-05-07T00:00:00+00:00",
            )
            candidate_id = created_groups[0].ranking[0]["candidate_id"]
            candidate_dir = group_store.candidate_dir(created_groups[0].group_id, str(candidate_id))
            soundfont = base / "soundfont.sf2"
            soundfont.write_bytes(b"sf2")

            def fake_runner(cmd, capture_output, text, timeout, shell):
                wav_path = Path(cmd[cmd.index("-F") + 1])
                wav_path.write_bytes(b"RIFFfakeWAVE")
                class Result:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return Result()

            original_render_audio = candidate_groups_module.render_audio
            try:
                candidate_groups_module.render_audio = lambda midi, wav, cfg: original_render_audio(midi, wav, cfg, runner=fake_runner)
                audio_candidate = group_store.render_candidate_audio(
                    created_groups[0].group_id,
                    str(candidate_id),
                    RendererConfig(soundfont_path=str(soundfont)),
                )
            finally:
                candidate_groups_module.render_audio = original_render_audio
            usage_report = build_provider_usage_report(
                scope="project",
                project_id=project_id,
                records=collect_project_provider_usage_records(project_id, document.versions, project_dir),
            )
            serialized = str([group.to_dict() for group in created_groups]) + str(usage_report)
            ok = (
                len(created_groups) == 2
                and len(ab.group_ids) == 2
                and candidate_midi_path(candidate_dir).read_bytes().startswith(b"MThd")
                and audio_candidate.audio_status == "completed"
                and candidate_audio_path(candidate_dir).read_bytes().startswith(b"RIFF")
                and usage_report["total_calls"] == 2
                and usage_report["total_tokens"] == 40
                and usage_report["estimated_cost"] is None
                and "sk-release-secret" not in serialized
            )
            return ok, f"groups={len(created_groups)}, ab={ab.ab_id}, midi={candidate_midi_path(candidate_dir).stat().st_size}, wav={audio_candidate.audio_size_bytes}, tokens={usage_report['total_tokens']}, cost={usage_report['estimated_cost']}"
    except Exception as exc:
        return False, str(exc)


def _v16_creative_assets_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v16-") as temp_dir:
            base = Path(temp_dir)
            store = ProjectStore(base / ".musicforge" / "projects")
            asset_store = AssetStore(base / ".musicforge" / "assets")
            document = store.create_project("Release v1.6 Smoke")
            request = SongRequest(
                title="Release v1.6 Smoke",
                language="en",
                style="synth pop",
                theme="creative asset smoke",
                tempo_bpm=100,
            )
            parent_dir = base / "runs" / "v16-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            document = store.add_version_from_job(
                document.state.project_id,
                _SmokeJob("v16-parent", parent_dir, request.to_dict()),
                name="Parent",
            )
            payloads = extract_assets_from_song_plan(
                parent_plan,
                {"source_type": "project_version", "project_id": document.state.project_id, "version_id": "v001", "job_id": "v16-parent", "style": request.style},
                {"asset_types": ["motif"], "section_name": "chorus", "tags": ["release"], "favorite": True},
            )
            asset = asset_store.create_asset(payloads[0], now="2026-05-07T00:00:00+00:00")
            asset = asset_store.render_asset_midi(asset.asset_id)
            asset_refs = [{"asset_id": asset.asset_id, "role": "motif_reference", "strength": 0.9}]
            child_dir = base / "runs" / "v16-child"
            child_plan = apply_asset_refs_to_plan(deterministic_compose(request), asset_store, asset_refs)
            write_json(child_dir / "data" / "song-plan.json", child_plan.to_dict())
            write_json(child_dir / "data" / "run-summary.json", {"title": child_plan.title})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(child_plan, child_dir / "renders" / "song.mid")
            snapshot = {
                "schema_version": 1,
                "asset_refs": asset_store.mark_used(asset_refs, {"usage_type": "release_check", "project_id": document.state.project_id, "version_id": "v002"}),
                "captured_at": "2026-05-07T00:00:00+00:00",
            }
            write_asset_refs_snapshot(child_dir, snapshot)
            child_job = _SmokeJob("v16-child", child_dir, request.to_dict() | {"asset_refs": asset_refs})
            child_job.artifacts["asset_refs"] = str(child_dir / "data" / "asset-refs.json")
            document = store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Asset Child",
                parent_version_id="v001",
                variant_type="manual",
                change_summary="reuse motif asset",
            )
            project_export = store.export_project(document.state.project_id)
            gate = evaluate_quality_gate(child_dir, QualityGateConfig(), now="2026-05-07T00:00:00+00:00")
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=store.project_dir(document.state.project_id),
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v002"),
                now="2026-05-07T00:00:00+00:00",
                project_export=project_export,
            )
            serialized = str(project_export.get("asset_refs")) + str(manifest.get("asset_refs"))
            ok = (
                asset.preview["midi_status"] == "completed"
                and (child_dir / "data" / "asset-refs.json").exists()
                and asset_store.read_asset(asset.asset_id).usage_count == 1
                and project_export["asset_refs"][0]["asset_id"] == asset.asset_id
                and manifest["asset_refs"][0]["asset_id"] == asset.asset_id
                and ".musicforge/provider.json" not in serialized
                and "sk-" not in serialized
                and str(base) not in serialized
            )
            return ok, f"asset={asset.asset_id}, usage={asset_store.read_asset(asset.asset_id).usage_count}, export_refs={len(project_export['asset_refs'])}, final_refs={len(manifest['asset_refs'])}"
    except Exception as exc:
        return False, str(exc)


def _v17_reference_library_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v17-") as temp_dir:
            base = Path(temp_dir)
            project_store = ProjectStore(base / ".musicforge" / "projects")
            reference_store = ReferenceStore(base / ".musicforge" / "references")
            asset_store = AssetStore(base / ".musicforge" / "assets")
            document = project_store.create_project("Release v1.7 Smoke")
            request = SongRequest(
                title="Release v1.7 Smoke",
                language="en",
                style="synth pop",
                theme="reference library smoke",
                tempo_bpm=102,
            )
            parent_dir = base / "runs" / "v17-parent"
            parent_plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_dir / "renders" / "song.mid")
            document = project_store.add_version_from_job(
                document.state.project_id,
                _SmokeJob("v17-parent", parent_dir, request.to_dict()),
                name="Parent",
            )
            reference, duplicate = reference_store.import_reference(
                {
                    "reference_type": "style_note",
                    "filename": "style.md",
                    "title": "Reference Style Seed",
                    "tags": ["release"],
                    "content_base64": "YXBpX2tleT1zay1yZWxlYXNlLXNlY3JldCB1c2UgaG9vayBmcm9tIEM6XFVzZXJzXGJhZFxzb25nLndhdg==",
                    "source_note": "Authorization: Bearer release-token-value D:\\Music\\private\\song.wav",
                    "license_note": "github_pat_123456789012345678901234 and /Users/bad/private/ref.wav plus \\\\server\\share\\client\\ref.wav",
                    "metadata": {"path": str(base), "api_key": "sk-release-secret", "note": "safe"},
                },
                now="2026-05-08T00:00:00+00:00",
            )
            duplicate_ref, duplicate_again = reference_store.import_reference(
                {
                    "reference_type": "style_note",
                    "filename": "copy.md",
                    "content_base64": "YXBpX2tleT1zay1yZWxlYXNlLXNlY3JldCB1c2UgaG9vayBmcm9tIEM6XFVzZXJzXGJhZFxzb25nLndhdg==",
                },
                now="2026-05-08T00:00:00+00:00",
            )
            reference_store.link_project(reference.reference_id, document.state.project_id)
            asset = reference_store.create_asset_from_reference(reference.reference_id, {"asset_type": "section_template"}, asset_store)
            refs = [{"reference_id": reference.reference_id, "role": "reference_style", "strength": 0.8}]
            snapshot = reference_refs_snapshot(reference_store, refs, captured_at="2026-05-08T00:00:00+00:00")
            child_dir = base / "runs" / "v17-child"
            child_plan = deterministic_compose(request)
            write_json(child_dir / "data" / "song-plan.json", child_plan.to_dict())
            write_json(child_dir / "data" / "run-summary.json", {"title": child_plan.title})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(child_plan, child_dir / "renders" / "song.mid")
            write_reference_refs_snapshot(child_dir, snapshot)
            reference_store.mark_used(refs, {"usage_type": "release_check", "project_id": document.state.project_id, "version_id": "v002"})
            child_job = _SmokeJob("v17-child", child_dir, request.to_dict() | {"reference_refs": refs})
            child_job.artifacts["reference_refs"] = str(child_dir / "data" / "reference-refs.json")
            document = project_store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Reference Child",
                parent_version_id="v001",
                variant_type="manual",
                change_summary="use reference material",
            )
            project_export = project_store.export_project(document.state.project_id)
            gate = evaluate_quality_gate(child_dir, QualityGateConfig(), now="2026-05-08T00:00:00+00:00")
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=project_store.project_dir(document.state.project_id),
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v002"),
                now="2026-05-08T00:00:00+00:00",
                project_export=project_export,
            )
            final_export_dir = project_store.project_dir(document.state.project_id) / "final-export"
            serialized = str(project_export.get("reference_refs")) + str(manifest.get("reference_refs")) + str(asset)
            ok = (
                not duplicate
                and duplicate_again
                and duplicate_ref.reference_id == reference.reference_id
                and asset["asset_type"] == "section_template"
                and (child_dir / "data" / "reference-refs.json").exists()
                and reference_store.read_reference(reference.reference_id).usage_count == 1
                and project_export["reference_refs"][0]["reference_id"] == reference.reference_id
                and manifest["reference_refs"][0]["reference_id"] == reference.reference_id
                and (final_export_dir / "references" / f"{reference.reference_id}.json").exists()
                and not any((final_export_dir / "references").glob("*.wav"))
                and "sk-release-secret" not in serialized
                and "release-token-value" not in serialized
                and "github_pat_123456789012345678901234" not in serialized
                and "/Users/bad" not in serialized
                and "C:\\Users\\bad" not in serialized
                and "D:\\Music" not in serialized
                and "\\\\server\\share" not in serialized
                and "api_key" not in serialized
                and str(base) not in serialized
            )
            return ok, f"reference={reference.reference_id}, duplicate={duplicate_again}, asset={asset['asset_id']}, export_refs={len(project_export['reference_refs'])}, final_refs={len(manifest['reference_refs'])}"
    except Exception as exc:
        return False, str(exc)


def _v18_reference_analysis_smoke(root: Path) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="musicforge-v18-") as temp_dir:
            base = Path(temp_dir)
            project_store = ProjectStore(base / ".musicforge" / "projects")
            reference_store = ReferenceStore(base / ".musicforge" / "references")
            asset_store = AssetStore(base / ".musicforge" / "assets")
            request = SongRequest(
                title="Release v1.8 Smoke",
                language="en",
                style="synth pop",
                theme="reference analysis smoke",
                tempo_bpm=120,
            )
            document = project_store.create_project("Release v1.8 Smoke")
            parent_dir = base / "runs" / "v18-parent"
            plan = deterministic_compose(request)
            write_json(parent_dir / "data" / "song-plan.json", plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(plan, parent_dir / "renders" / "song.mid")
            document = project_store.add_version_from_job(document.state.project_id, _SmokeJob("v18-parent", parent_dir, request.to_dict()), name="Parent")

            wav_ref, _ = reference_store.import_reference(
                {
                    "reference_type": "audio_wav",
                    "filename": "tiny.wav",
                    "title": "Tiny WAV",
                    "content_base64": base64.b64encode(_tiny_wav_bytes()).decode("ascii"),
                    "license_note": "api_key=sk-v18-secret D:\\Music\\private\\tiny.wav",
                },
                now="2026-05-08T00:00:00+00:00",
            )
            midi_ref, _ = reference_store.import_reference(
                {
                    "reference_type": "midi",
                    "filename": "seed.mid",
                    "title": "MIDI Seed",
                    "content_base64": base64.b64encode(_tiny_reference_midi_bytes()).decode("ascii"),
                    "source_note": "Authorization: Bearer v18-token \\\\server\\share\\seed.mid",
                },
                now="2026-05-08T00:00:00+00:00",
            )
            wav_report = analyze_reference(reference_store, wav_ref.reference_id, now="2026-05-08T00:00:00+00:00")
            midi_report = analyze_reference(reference_store, midi_ref.reference_id, now="2026-05-08T00:00:00+00:00")
            slices = generate_slices(reference_store, midi_ref.reference_id, now="2026-05-08T00:00:00+00:00")
            slice_id = slices["slices"][0]["slice_id"]
            rendered = render_reference_slice_midi(reference_store, midi_ref.reference_id, slice_id, now="2026-05-08T00:00:00+00:00")
            asset = create_asset_from_slice(reference_store, midi_ref.reference_id, slice_id, {"name": "Release slice"}, asset_store, now="2026-05-08T00:00:00+00:00")
            refs = [{"reference_id": wav_ref.reference_id}, {"reference_id": midi_ref.reference_id}]
            snapshot = reference_refs_snapshot(reference_store, refs, captured_at="2026-05-08T00:00:00+00:00")
            child_dir = base / "runs" / "v18-child"
            child_plan = deterministic_compose(request)
            write_json(child_dir / "data" / "song-plan.json", child_plan.to_dict())
            write_json(child_dir / "data" / "run-summary.json", {"title": child_plan.title})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(child_plan, child_dir / "renders" / "song.mid")
            write_reference_refs_snapshot(child_dir, snapshot)
            child_job = _SmokeJob("v18-child", child_dir, request.to_dict() | {"reference_refs": refs})
            child_job.artifacts["reference_refs"] = str(child_dir / "data" / "reference-refs.json")
            document = project_store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Reference Analysis Child",
                parent_version_id="v001",
                variant_type="manual",
                change_summary="use analyzed reference material",
            )
            project_export = project_store.export_project(document.state.project_id)
            gate = evaluate_quality_gate(child_dir, QualityGateConfig(), now="2026-05-08T00:00:00+00:00")
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=project_store.project_dir(document.state.project_id),
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v002"),
                now="2026-05-08T00:00:00+00:00",
                project_export=project_export,
            )
            serialized = str(snapshot) + str(project_export.get("reference_refs")) + str(manifest.get("reference_refs")) + str(asset)
            ok = (
                wav_report["summary"].get("duration_seconds", 0) > 0
                and wav_report["summary"].get("envelope")
                and midi_report["summary"].get("track_count") == 3
                and slices["slices"]
                and rendered["slice"]["midi_status"] == "completed"
                and asset["content"].get("notes")
                and "analysis_summary" in snapshot["reference_refs"][0]
                and "analysis_summary" in project_export["reference_refs"][0]
                and "analysis_summary" in manifest["reference_refs"][0]
                and "sk-v18-secret" not in serialized
                and "v18-token" not in serialized
                and "D:\\Music" not in serialized
                and "\\\\server\\share" not in serialized
                and "content_base64" not in serialized
            )
            return ok, f"wav={wav_ref.reference_id}, midi={midi_ref.reference_id}, slices={len(slices['slices'])}, asset={asset['asset_id']}"
    except Exception as exc:
        return False, str(exc)


def _v19_library_context_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        try:
            project_store = ProjectStore(base / ".musicforge" / "projects")
            reference_store = ReferenceStore(base / ".musicforge" / "references")
            asset_store = AssetStore(base / ".musicforge" / "assets")
            context_store = ContextPackStore(base / ".musicforge" / "context-packs")
            library_store = LibraryIndexStore(base / ".musicforge" / "library")
            request = SongRequest(
                title="Release v1.9 Smoke",
                language="English",
                style="rainy synth pop",
                theme="rainy hook context",
                tempo_bpm=120,
                key="C",
            )
            document = project_store.create_project("Release v1.9 Smoke")
            asset = asset_store.create_asset(
                {
                    "asset_type": "motif",
                    "name": "Rainy synth hook",
                    "description": "Reusable hook for rainy synth pop.",
                    "tags": ["rainy", "hook", "synth"],
                    "style": "synth pop",
                    "key": "C",
                    "tempo_bpm": 120,
                    "quality_score": 88,
                    "content": {"notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1}, {"pitch": 64, "start_beat": 1, "duration_beats": 1}]},
                    "source": {"source_type": "release_check", "path": "D:\\Music\\secret.mid"},
                },
                now="2026-05-08T00:00:00+00:00",
            )
            midi_ref, _ = reference_store.import_reference(
                {
                    "reference_type": "midi",
                    "filename": "seed.mid",
                    "title": "Rainy MIDI Reference",
                    "tags": ["rainy", "midi"],
                    "content_base64": base64.b64encode(_tiny_reference_midi_bytes()).decode("ascii"),
                    "source_note": "Bearer v19-token \\\\server\\share\\seed.mid",
                },
                now="2026-05-08T00:00:00+00:00",
            )
            analyze_reference(reference_store, midi_ref.reference_id, now="2026-05-08T00:00:00+00:00")
            generate_slices(reference_store, midi_ref.reference_id, now="2026-05-08T00:00:00+00:00")
            index = library_store.rebuild(asset_store, reference_store, now="2026-05-08T00:00:00+00:00")
            results = search_library(index, {"query": "rainy hook synth", "roles": ["hook"], "tempo_bpm": 120, "key": "C"})
            recommendation = recommend_library_context(index, {"source": "song_request", "goal": "generate", "song_request": request.to_dict()})
            preview = recommendation["recommendation"]["context_pack_preview"]
            pack = context_store.create_pack(
                {
                    "name": "Release Context",
                    "created_from": {"source": "song_request", "goal": "generate"},
                    "query": recommendation["recommendation"]["query"],
                    "asset_refs": preview["asset_refs"][:1],
                    "reference_refs": preview["reference_refs"][:1],
                    "selection": {"mode": "recommended", "selected_by": "system"},
                },
                asset_store=asset_store,
                reference_store=reference_store,
                now="2026-05-08T00:00:00+00:00",
            )
            applied = context_store.apply_preview(pack.pack_id, asset_store=asset_store, reference_store=reference_store, captured_at="2026-05-08T00:00:00+00:00")
            child_dir = base / "runs" / "v19-child"
            child_plan = apply_asset_refs_to_plan(deterministic_compose(request), asset_store, applied["asset_refs"])
            write_json(child_dir / "data" / "song-plan.json", child_plan.to_dict())
            write_json(child_dir / "data" / "run-summary.json", {"title": child_plan.title})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(child_plan, child_dir / "renders" / "song.mid")
            write_asset_refs_snapshot(child_dir, {"schema_version": 1, "asset_refs": applied["asset_refs"], "captured_at": "2026-05-08T00:00:00+00:00"})
            write_reference_refs_snapshot(child_dir, {"schema_version": 1, "reference_refs": applied["reference_refs"], "captured_at": "2026-05-08T00:00:00+00:00"})
            write_context_pack_snapshot(child_dir, context_pack_snapshot(pack, applied, captured_at="2026-05-08T00:00:00+00:00"))
            child_job = _SmokeJob("v19-child", child_dir, request.to_dict() | {"context_pack_id": pack.pack_id, "context_pack": context_pack_snapshot(pack, applied)})
            child_job.artifacts["asset_refs"] = str(child_dir / "data" / "asset-refs.json")
            child_job.artifacts["reference_refs"] = str(child_dir / "data" / "reference-refs.json")
            child_job.artifacts["context_pack"] = str(child_dir / "data" / "context-pack.json")
            document = project_store.add_version_from_job(
                document.state.project_id,
                child_job,
                name="Library Context Child",
                variant_type="manual",
                change_summary="use library context pack",
            )
            project_export = project_store.export_project(document.state.project_id)
            gate = evaluate_quality_gate(child_dir, QualityGateConfig(), now="2026-05-08T00:00:00+00:00")
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=project_store.project_dir(document.state.project_id),
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(version_id="v001"),
                now="2026-05-08T00:00:00+00:00",
                project_export=project_export,
            )
            serialized = str(results) + str(recommendation) + str(project_export.get("context_packs")) + str(manifest.get("context_pack"))
            ok = (
                index.summary()["item_count"] == 2
                and results["results"]
                and results["results"][0]["score_breakdown"]
                and pack.pack_id == "pack-001"
                and applied["asset_refs"]
                and applied["reference_refs"]
                and project_export["context_packs"][0]["pack_id"] == pack.pack_id
                and manifest["context_pack"]["pack_id"] == pack.pack_id
                and "v19-token" not in serialized
                and "D:\\Music" not in serialized
                and "\\\\server\\share" not in serialized
                and "content_base64" not in serialized
            )
            return ok, f"index_items={index.summary()['item_count']}, results={len(results['results'])}, pack={pack.pack_id}, assets={len(applied['asset_refs'])}, references={len(applied['reference_refs'])}"
        except Exception as exc:
            return False, str(exc)


def _v20_visual_editor_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        try:
            project_store = ProjectStore(base / ".musicforge" / "projects")
            request = SongRequest(
                title="Release v2.0 Smoke",
                language="English",
                style="synth pop",
                theme="visual editor",
                tempo_bpm=120,
                key="C",
            )
            parent_plan = deterministic_compose(request)
            parent_dir = base / "runs" / "v20-parent"
            parent_plan_path = parent_dir / "data" / "song-plan.json"
            parent_midi_path = parent_dir / "renders" / "song.mid"
            write_json(parent_plan_path, parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_midi_path)
            document = project_store.create_project("Release v2.0 Smoke")
            document = project_store.add_version_from_job(document.state.project_id, _SmokeJob("v20-parent", parent_dir, request.to_dict()), name="Parent")
            state = build_editor_state(parent_plan)
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            result = apply_editor_patch(
                parent_plan,
                {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "label": "Release editor patch",
                    "operations": [
                        {"op": "set_section_chords", "section_id": "section-001", "chords": ["Cmaj7", "G7", "Am7", "Fmaj7"]},
                        {"op": "set_track_instrument", "track_id": "track-001", "instrument": "warm lead synth"},
                        {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"pitch": 67, "velocity": 96}},
                    ],
                },
            )
            preview_store = EditorPreviewStore(project_store.project_dir(document.state.project_id))
            preview, preview_dir = preview_store.create_preview(
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v20-parent",
                parent_plan=parent_plan,
                patch=result.patch,
                result=result,
                now="2026-05-08T00:00:00+00:00",
            )
            child_dir = base / "runs" / "v20-child"
            child_plan_path = child_dir / "data" / "song-plan.json"
            child_midi_path = child_dir / "renders" / "song.mid"
            metadata = editor_edit_metadata(
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v20-parent",
                preview_id=preview.preview_id,
                patch=result.patch,
                result=result,
                created_at="2026-05-08T00:00:00+00:00",
            )
            write_json(child_plan_path, result.plan.to_dict())
            write_json(child_dir / "data" / "editor-patch.json", result.patch.to_dict())
            write_json(child_dir / "data" / "edit-metadata.json", metadata)
            write_json(child_dir / "data" / "run-summary.json", {"title": result.plan.title, "edit": metadata["summary"]})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(result.plan, child_midi_path)
            document = project_store.add_version_from_job(
                document.state.project_id,
                _SmokeJob("v20-child", child_dir, request.to_dict() | {"edit_type": "manual_editor_edit"}),
                name="Editor Child",
                parent_version_id="v001",
                variant_type="manual_editor_edit",
                change_summary="visual editor patch",
            )
            preview_store.mark_applied(preview.preview_id, version_id="v002", job_id="v20-child", now="2026-05-08T00:00:00+00:00")
            compare = compare_project_versions(document, "v001", "v002")
            project_export = project_store.export_project(document.state.project_id)
            ok = (
                state["sections"][0]["section_id"] == "section-001"
                and preview.preview_id == "preview-001"
                and (preview_dir / "song.mid").exists()
                and metadata["edit_source"] == "visual_editor"
                and metadata["operation_count"] == 3
                and document.versions[-1].variant_type == "manual_editor_edit"
                and compare["right"]["edit"]["edit_source"] == "visual_editor"
                and project_export["versions"][1]["variant_type"] == "manual_editor_edit"
                and child_midi_path.exists()
                and parent_plan_path.read_bytes()
            )
            return ok, f"preview={preview.preview_id}, version={document.versions[-1].version_id}, ops={metadata['operation_count']}, tracks={len(metadata['changed_tracks'])}"
        except Exception as exc:
            return False, str(exc)


def _v21_structure_editor_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        try:
            project_store = ProjectStore(base / ".musicforge" / "projects")
            request = SongRequest(
                title="Release v2.1 Smoke",
                language="English",
                style="synth pop",
                theme="structure editor",
                tempo_bpm=120,
                key="C",
            )
            parent_plan = deterministic_compose(request)
            parent_dir = base / "runs" / "v21-parent"
            parent_plan_path = parent_dir / "data" / "song-plan.json"
            parent_midi_path = parent_dir / "renders" / "song.mid"
            write_json(parent_plan_path, parent_plan.to_dict())
            write_json(parent_dir / "data" / "run-summary.json", {"title": parent_plan.title})
            write_json(parent_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(parent_plan, parent_midi_path)
            document = project_store.create_project("Release v2.1 Smoke")
            document = project_store.add_version_from_job(document.state.project_id, _SmokeJob("v21-parent", parent_dir, request.to_dict()), name="Parent")
            parent_bytes = parent_plan_path.read_bytes()
            state = build_editor_state(parent_plan)
            result = apply_editor_patch(
                parent_plan,
                {
                    "schema_version": 1,
                    "base_plan_hash": state["base_plan_hash"],
                    "label": "Structure editor patch sk-release-secret",
                    "operations": [
                        {"op": "duplicate_section", "section_id": "section-003", "name": "chorus 2", "copy_notes": True, "after_section_id": "section-003"},
                        {"op": "resize_section", "section_id": "section-002", "bars": 4, "note_policy": "crop"},
                        {"op": "add_track", "name": "pad", "instrument": "warm pad"},
                        {"op": "duplicate_track", "track_id": "track-001", "name": "counter melody", "transpose": 12},
                        {"op": "rename_track", "track_id": "track-002", "name": "chords keys"},
                    ],
                },
            )
            preview_store = EditorPreviewStore(project_store.project_dir(document.state.project_id))
            preview, _preview_dir = preview_store.create_preview(
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v21-parent",
                parent_plan=parent_plan,
                patch=result.patch,
                result=result,
                now="2026-05-08T00:00:00+00:00",
            )
            child_dir = base / "runs" / "v21-child"
            child_plan_path = child_dir / "data" / "song-plan.json"
            child_midi_path = child_dir / "renders" / "song.mid"
            metadata = editor_edit_metadata(
                project_id=document.state.project_id,
                parent_version_id="v001",
                parent_job_id="v21-parent",
                preview_id=preview.preview_id,
                patch=result.patch,
                result=result,
                created_at="2026-05-08T00:00:00+00:00",
            )
            write_json(child_plan_path, result.plan.to_dict())
            write_json(child_dir / "data" / "editor-patch.json", result.patch.to_dict())
            write_json(child_dir / "data" / "edit-metadata.json", metadata)
            write_json(child_dir / "data" / "run-summary.json", {"title": result.plan.title, "edit": metadata["summary"]})
            write_json(child_dir / "data" / "validator-report.json", {"status": "passed"})
            render_midi(result.plan, child_midi_path)
            document = project_store.add_version_from_job(
                document.state.project_id,
                _SmokeJob("v21-child", child_dir, request.to_dict() | {"edit_type": "manual_editor_edit"}),
                name="Structure Child",
                parent_version_id="v001",
                variant_type="manual_editor_edit",
                change_summary="structure editor patch",
            )
            preview_store.mark_applied(preview.preview_id, version_id="v002", job_id="v21-child", now="2026-05-08T00:00:00+00:00")
            history = preview_store.list_previews()
            patch_summary = preview_store.read_patch_summary(preview.preview_id)
            cleanup = preview_store.cleanup_previews(delete_unapplied_older_than_days=0, keep_latest=5, now="2026-05-09T00:00:00+00:00")
            compare = compare_project_versions(document, "v001", "v002")
            project_export = project_store.export_project(document.state.project_id)
            gate = evaluate_quality_gate(
                child_dir,
                QualityGateConfig(
                    min_overall=0,
                    min_structure=0,
                    min_melody=0,
                    min_harmony=0,
                    min_arrangement=0,
                    require_audio=False,
                    require_stems=False,
                ),
                now="2026-05-08T00:00:00+00:00",
            )
            manifest = build_final_export_bundle(
                project=document.state,
                version=document.versions[-1],
                project_dir=project_store.project_dir(document.state.project_id),
                run_dir=child_dir,
                gate=gate,
                options=FinalExportOptions(include_audio=False, include_stems=False),
                now="2026-05-08T00:00:00+00:00",
                project_export=project_export,
            )
            section_starts = [section.start_bar for section in result.plan.sections]
            serialized = str(project_export) + str(manifest) + str(patch_summary)
            ok = (
                preview.preview_id == "preview-001"
                and len(result.plan.sections) == len(parent_plan.sections) + 1
                and len(result.plan.tracks) == len(parent_plan.tracks) + 2
                and section_starts == sorted(section_starts)
                and parent_plan_path.read_bytes() == parent_bytes
                and document.versions[-1].variant_type == "manual_editor_edit"
                and compare["right"]["edit"]["structure"]["section_operations"]["duplicate_section"] == 1
                and project_export["versions"][1]["edit"]["structure"]["track_operations"]["add_track"] == 1
                and manifest["edit"]["structure"]["section_operations"]["resize_section"] == 1
                and history[0].preview_id == preview.preview_id
                and cleanup["deleted_count"] == 0
                and "sk-release-secret" not in serialized
            )
            return ok, f"preview={preview.preview_id}, version={document.versions[-1].version_id}, sections={len(result.plan.sections)}, tracks={len(result.plan.tracks)}, operations={metadata['operation_count']}"
        except Exception as exc:
            return False, str(exc)


def _v22_interactive_editor_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.2 HTTP Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.2 HTTP Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "interactive editor",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            first_status, first = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-draft",
                {
                    "include_view": True,
                    "include_diff": True,
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "operations": [{"op": "delete_section", "section_id": "section-001", "note_policy": "shift_left"}],
                    },
                },
            )
            visible_section = first["view"]["sections"][0]
            visible_note = first["view"]["lanes"][0]["notes"][0]
            note_id = visible_note["note_id"]
            second_patch = {
                "schema_version": 1,
                "base_plan_hash": state["base_plan_hash"],
                "label": "Interactive editor patch",
                "operations": [
                    {"op": "delete_section", "section_id": "section-001", "note_policy": "shift_left"},
                    {"op": "resize_section", "section_id": visible_section["section_id"], "bars": 4, "note_policy": "crop"},
                    {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 76}},
                    {"op": "move_notes", "track_id": "track-001", "note_ids": [note_id], "delta_beats": 0.5},
                    {"op": "transpose_notes", "track_id": "track-001", "note_ids": [note_id], "semitones": 1},
                    {"op": "add_note", "track_id": "track-001", "note": {"pitch": 72, "start_beat": 2.5, "duration_beats": 0.5, "velocity": 88}},
                ],
            }
            second_status, second = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-draft",
                {"include_view": True, "include_diff": True, "patch": second_patch},
            )
            history_status, history = _release_http_json(server, "GET", f"/api/projects/{project_id}/editor-previews")
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {"patch": second_patch, "render_midi": True},
            )
            preview = preview_data["preview"]
            midi_status, midi = _release_http_bytes(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/midi")
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/apply",
                {"version_name": "Interactive Child", "version_note": "release smoke"},
            )
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            moved_note = next(note for note in second["view"]["lanes"][0]["notes"] if note["note_id"] == note_id)
            derived_notes = [note for note in second["view"]["lanes"][0]["notes"] if str(note.get("note_id", "")).startswith("derived-note-")]
            child_midi_path = Path(applied["job"]["output_dir"]) / "renders" / "song.mid"
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and first_status == 200
                and first["view"]["sections"][0]["section_id"] != "section-001"
                and visible_section["section_id"] == "section-002"
                and second_status == 200
                and "verse" in second["summary"]["changed_sections"]
                and history_status == 200
                and history["previews"] == []
                and preview_status == 201
                and preview["preview_id"] == "preview-001"
                and midi_status == 200
                and midi.startswith(b"MThd")
                and apply_status == 201
                and applied["version"]["variant_type"] == "manual_editor_edit"
                and compare_status == 200
                and export_status == 200
                and moved_note["start_beat"] == visible_note["start_beat"] + 0.5
                and moved_note["pitch"] == visible_note["pitch"] + 1
                and len(second["view"]["lanes"][0]["notes"]) > 0
                and len(derived_notes) == 1
                and derived_notes[0]["editable"] is False
                and second["diff"]["notes"]["changed"] == 2
                and second["diff"]["notes"]["moved"] == 1
                and second["summary"]["operation_counts"]["add_note"] == 1
                and compare["right"]["edit"]["edit_source"] == "visual_editor"
                and project_export["versions"][1]["edit"]["summary"]["move_notes"] == 1
                and child_midi_path.exists()
            )
            return ok, f"preview={preview['preview_id']}, version={child_version}, visible_section={visible_section['section_id']}, draft_notes={len(second['view']['lanes'][0]['notes'])}, derived_notes={len(derived_notes)}, operations={second['operation_count']}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v23_editor_clip_insert_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            _created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.3 Clip Smoke"})
            project_id = created["project"]["project_id"]
            _version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.3 Clip Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "clip insert",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            asset = server.asset_store.create_asset(
                {
                    "asset_type": "motif",
                    "name": "Release Clip Motif",
                    "key": "C",
                    "tempo_bpm": 120,
                    "duration_beats": 2,
                    "content": {
                        "kind": "motif",
                        "notes": [
                            {"pitch": 72, "start_beat": 0, "duration_beats": 0.5, "velocity": 90},
                            {"pitch": 74, "start_beat": 0.5, "duration_beats": 0.5, "velocity": 88},
                        ],
                    },
                },
                now="2026-05-11T00:00:00+00:00",
            )
            _state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            clips_status, clips = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-clips")
            clip = next(item for item in clips["clips"] if item["source_type"] == "asset" and item["source_id"] == asset.asset_id)
            draft_status, draft = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-clip-draft",
                {
                    "clip_ref": clip["clip_ref"],
                    "target": {"track_id": "track-001", "section_id": "section-001", "start_beat": 0},
                    "options": {"mode": "overlay", "transpose": 1, "velocity_scale": 1, "quantize_grid": "1/16"},
                    "include_view": True,
                    "include_diff": True,
                },
            )
            patch = draft["patch"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {"patch": patch, "render_midi": True},
            )
            preview = preview_data["preview"]
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/apply",
                {"version_name": "Clip Child", "version_note": "clip smoke"},
            )
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            edit_metadata = Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(edit_metadata.read_text(encoding="utf-8"))
            derived_notes = [
                note
                for lane in draft["draft_view"]["lanes"]
                for note in lane["notes"]
                if str(note.get("note_id", "")).startswith("derived-note-")
            ]
            serialized = json.dumps({"metadata": metadata, "export": project_export, "compare": compare}, ensure_ascii=False)
            ok = (
                parent_job["status"] == "completed"
                and clips_status == 200
                and draft_status == 200
                and draft["clip_summary"]["source_type"] == "asset"
                and len(patch["operations"]) == 2
                and len(patch["metadata"]["clip_inserts"]) == 1
                and len(derived_notes) >= 2
                and preview_status == 201
                and apply_status == 201
                and applied["version"]["variant_type"] == "manual_editor_edit"
                and metadata["edit_type"] == "visual_editor_clip_insert"
                and metadata["clip_inserts"][0]["source_id"] == asset.asset_id
                and compare_status == 200
                and compare["right"]["edit"]["clip_inserts"][0]["source_id"] == asset.asset_id
                and export_status == 200
                and project_export["versions"][1]["edit"]["clip_inserts"][0]["source_id"] == asset.asset_id
                and "sk-release-secret" not in serialized
            )
            return ok, f"asset={asset.asset_id}, version={child_version}, clip_ops={len(patch['operations'])}, derived_notes={len(derived_notes)}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v24_editor_template_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.4 Template Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.4 Template Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "template insert",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            section_status, section_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/section-templates",
                {"section_id": "section-001", "name": "Release Chorus Lift", "tags": ["release", "template"]},
            )
            template = section_data["template"]
            list_status, templates = _release_http_json(server, "GET", "/api/editor-templates")
            mapping_status, mapping = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-template-mapping",
                {"source_ref": {"source_type": "section_template", "template_id": template["template_id"]}},
            )
            lane_mappings = [
                {"lane_id": item["lane_id"], "target_track_id": item["suggested_track_id"], "mode": "overlay"}
                for item in mapping["suggestions"]
                if item.get("suggested_track_id")
            ][:2]
            draft_status, draft = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-multitrack-clip-draft",
                {
                    "source_ref": {"source_type": "section_template", "template_id": template["template_id"]},
                    "target": {"section_id": "section-002", "start_beat": 16},
                    "lane_mappings": lane_mappings,
                    "options": {"mode": "overlay", "transpose": 1, "velocity_scale": 1, "quantize_grid": "1/16"},
                    "include_view": True,
                    "include_diff": True,
                },
            )
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {"patch": draft["combined_patch"], "render_midi": True},
            )
            preview = preview_data["preview"]
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/apply",
                {"version_name": "Template Child", "version_note": "template smoke"},
            )
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"force": True})
            metadata_path = Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            derived_notes = [
                note
                for lane in draft["draft_view"]["lanes"]
                for note in lane["notes"]
                if str(note.get("note_id", "")).startswith("derived-note-")
            ]
            add_tracks = {operation["track_id"] for operation in draft["patch"]["operations"] if operation.get("op") == "add_note"}
            serialized = json.dumps({"metadata": metadata, "export": project_export, "compare": compare, "final_export": final_export}, ensure_ascii=False)
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and section_status == 201
                and template["template_id"] == "section-template-001"
                and list_status == 200
                and templates["section_templates"]
                and mapping_status == 200
                and len(lane_mappings) >= 2
                and draft_status == 200
                and draft["template_summary"]["source_type"] == "section_template"
                and len(add_tracks) >= 2
                and len(derived_notes) >= 2
                and draft["combined_patch"]["metadata"]["template_inserts"][0]["source_id"] == template["template_id"]
                and preview_status == 201
                and apply_status == 201
                and metadata["edit_type"] == "visual_editor_template_insert"
                and metadata["template_inserts"][0]["source_id"] == template["template_id"]
                and compare_status == 200
                and compare["right"]["edit"]["template_inserts"][0]["source_id"] == template["template_id"]
                and export_status == 200
                and project_export["versions"][1]["edit"]["template_inserts"][0]["source_id"] == template["template_id"]
                and final_status == 200
                and final_data["project"]["final_version_id"] == child_version
                and final_export_status == 200
                and final_export["final_export"]["edit"]["template_inserts"][0]["source_id"] == template["template_id"]
                and "sk-release-secret" not in serialized
                and str(base) not in serialized
            )
            return ok, f"template={template['template_id']}, version={child_version}, lanes={len(lane_mappings)}, tracks={len(add_tracks)}, derived_notes={len(derived_notes)}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v25_editor_audition_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.5 Audition Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.5 Audition Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "audition",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Audition release patch",
                        "operations": [
                            {"op": "set_section_lyrics", "section_id": "section-002", "lyrics": "release audition changed section"},
                            {"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 97}},
                        ],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            parent_audition_status, parent_audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "parent", "range": {"mode": "full_song"}, "track_mode": "all"},
            )
            changed_audition_status, changed_audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "changed_sections"}, "track_mode": "all"},
            )
            solo_audition_status, solo_audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-001"]},
            )
            listing_status, listing = _release_http_json(server, "GET", f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions")
            midi_status, midi = _release_http_bytes(
                server,
                "GET",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{solo_audition['audition']['audition_id']}/midi",
            )
            render_audio_status, render_audio_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{solo_audition['audition']['audition_id']}/render-audio",
            )
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/apply",
                {"version_name": "Audition Child", "version_note": "audition smoke"},
            )
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            metadata_path = Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"metadata": metadata, "compare": compare, "export": project_export}, ensure_ascii=False)
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and parent_audition_status == 201
                and changed_audition_status == 201
                and solo_audition_status == 201
                and listing_status == 200
                and len(listing["auditions"]) == 3
                and midi_status == 200
                and midi.startswith(b"MThd")
                and render_audio_status == 400
                and "soundfont_path is required" in render_audio_data.get("error", "")
                and apply_status == 201
                and metadata["audition_summary"]["audition_count"] == 3
                and compare_status == 200
                and compare["right"]["edit"]["audition_summary"]["audition_count"] == 3
                and export_status == 200
                and project_export["versions"][1]["edit"]["audition_summary"]["audition_count"] == 3
                and str(base) not in serialized
                and "soundfont" not in serialized.lower()
            )
            return ok, f"preview={preview['preview_id']}, version={child_version}, auditions={len(listing['auditions'])}, audio_status={render_audio_status}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v26_audition_review_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.6 Review Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.6 Review Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "audition review",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Review release patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 95}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            audition_status, audition_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-001"]},
            )
            audition_id = audition_data["audition"]["audition_id"]
            review_status, review = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                {"rating": 5, "status": "keep", "favorite": True, "notes": r"release hook api_key=sk-secret-value C:\Users\demo\hook.wav", "tags": ["hook"]},
            )
            marker_status, marker = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                {"beat": 1, "kind": "hook", "label": "release marker sk-secret-value"},
            )
            asset_status, asset = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/create-asset",
                {"asset_type": "motif", "track_id": "track-001", "name": "Release audition motif", "tags": ["audition"]},
            )
            board_status, board = _release_http_json(server, "GET", f"/api/projects/{project_id}/audition-reviews?favorite=true&min_rating=4&sort=rating")
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/apply",
                {"version_name": "Review Child", "version_note": "review smoke"},
            )
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            metadata_path = Path(applied["job"]["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"review": review, "marker": marker, "asset": asset, "board": board, "metadata": metadata, "compare": compare, "export": project_export}, ensure_ascii=False)
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and audition_status == 201
                and review_status == 200
                and marker_status == 201
                and asset_status == 201
                and board_status == 200
                and board["summary"]["favorite_count"] == 1
                and board["summary"]["best_rating"] == 5
                and board["summary"]["marker_count"] == 1
                and board["summary"]["asset_count"] == 1
                and apply_status == 201
                and metadata["audition_summary"]["best_rating"] == 5
                and metadata["audition_summary"]["asset_count"] == 1
                and compare_status == 200
                and compare["right"]["edit"]["audition_summary"]["best_rating"] == 5
                and export_status == 200
                and project_export["versions"][1]["edit"]["audition_summary"]["asset_count"] == 1
                and asset["asset"]["source"]["source_type"] == "editor_audition"
                and "sk-secret-value" not in serialized
                and "C:\\Users" not in serialized
            )
            return ok, f"preview={preview['preview_id']}, audition={audition_id}, asset={asset.get('asset', {}).get('asset_id')}, rating={board['summary'].get('best_rating')}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v27_review_edit_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.7 Review Edit Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.7 Review Edit Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "review edit",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Review edit patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 94}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            audition_status, audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "section", "section_id": "section-001"}, "track_mode": "solo", "track_ids": ["track-003"]},
            )
            audition_id = audition["audition"]["audition_id"]
            review_status, _review = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                {"rating": 4, "status": "needs_fix", "favorite": True, "notes": r"bass 太满, chorus 更强 api_key=sk-secret-value C:\Users\demo\song.wav", "tags": ["review"]},
            )
            marker_status, _marker = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                {"beat": 1, "kind": "fix", "label": "fix density"},
            )
            preview_edit_status, preview_edit = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-edit-preview",
            )
            edit_status, edit = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-edit",
                {"version_name": "Review Edit Child", "version_note": "review smoke"},
            )
            edit_job = _release_wait_http_job(server, edit["job"]["job_id"])
            child_version = edit["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            asset_status, asset = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/create-asset",
                {"asset_type": "motif", "track_id": "track-001", "name": "Review edit context motif"},
            )
            context_status, context = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/create-context-pack",
            )
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"preview_edit": preview_edit, "metadata": metadata, "compare": compare, "export": project_export, "context": context}, ensure_ascii=False)
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and audition_status == 201
                and review_status == 200
                and marker_status == 201
                and preview_edit_status == 201
                and len(preview_edit["review_edit"]["intents"]) >= 1
                and edit_status == 202
                and edit_job["status"] == "completed"
                and metadata["edit_source"] == "audition_review"
                and metadata["review_edit"]["audition_id"] == audition_id
                and compare_status == 200
                and compare["right"]["edit"]["review_edit"]["audition_id"] == audition_id
                and export_status == 200
                and project_export["versions"][1]["edit"]["review_edit"]["audition_id"] == audition_id
                and asset_status == 201
                and context_status == 201
                and context["context_pack"]["asset_refs"][0]["asset_id"] == asset["asset"]["asset_id"]
                and "sk-secret-value" not in serialized
                and "C:\\Users" not in serialized
            )
            return ok, f"preview={preview['preview_id']}, audition={audition_id}, version={child_version}, intents={len(preview_edit['review_edit']['intents'])}, pack={context.get('context_pack', {}).get('pack_id')}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v28_review_task_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.8 Review Task Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.8 Review Task Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "review task",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Review task patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 94}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            audition_status, audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]},
            )
            audition_id = audition["audition"]["audition_id"]
            review_status, _review = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                {"rating": 4, "status": "needs_fix", "favorite": True, "notes": r"bass 太满, chorus 更强 api_key=sk-secret-value C:\Users\demo\song.wav", "tags": ["review"]},
            )
            keep_status, _keep = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                {"beat": 0, "kind": "keep", "label": "keep hook"},
            )
            marker_status, _marker = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                {"beat": 1, "kind": "fix", "label": "fix density"},
            )
            task_status, task_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-task",
                {},
            )
            task = task_data["task"]
            task_id = task["task_id"]
            list_status, listing = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks")
            candidates_status, candidates_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-tasks/{task_id}/candidates",
                {"render_midi": True},
            )
            candidate = candidates_data["candidates"][0]
            candidate_id = candidate["candidate_id"]
            midi_status, midi = _release_http_bytes(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/midi")
            audio_status, audio_error = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/render-audio")
            candidate_json = base / ".musicforge" / "projects" / project_id / "review-tasks" / task_id / "candidates" / candidate_id / "candidate.json"
            original_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data["artifacts"]["midi_path"] = f"review-tasks/{task_id}/candidates/revcand-999/renders/song.mid"
            candidate_json.write_text(json.dumps(polluted_candidate_data), encoding="utf-8")
            polluted_midi_status, polluted_midi = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/midi")
            candidate_json.write_text(json.dumps(original_candidate_data), encoding="utf-8")
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply",
                {"version_name": "Review Task Child", "version_note": "review task smoke"},
            )
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            duplicate_status, duplicate = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply", {})
            detail_status, detail = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}")
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            needs_status, needs = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/needs-more-work", {"note": "still too dense"})
            follow_up_id = (needs.get("follow_up_task") or {}).get("task_id")
            follow_status, follow = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{follow_up_id}")
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"task": task_data, "metadata": metadata, "compare": compare, "export": project_export, "final": final_export, "needs": needs}, ensure_ascii=False)
            ok = (
                created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and audition_status == 201
                and review_status == 200
                and keep_status == 201
                and marker_status == 201
                and task_status == 201
                and task["target"]["marker_kind"] == "fix"
                and task["target"]["section_name"] == "verse"
                and task["target"]["global_marker_beat"] == 17.0
                and list_status == 200
                and listing["summary"]["total"] == 1
                and candidates_status == 201
                and len(candidates_data["candidates"]) >= 2
                and candidates_data["task"]["status"] == "candidate_ready"
                and midi_status == 200
                and midi.startswith(b"MThd")
                and audio_status == 400
                and "soundfont_path is required" in audio_error.get("error", "")
                and polluted_midi_status == 409
                and "unsafe" in polluted_midi.get("error", "")
                and apply_status == 202
                and edit_job["status"] == "completed"
                and applied["task"]["status"] == "applied"
                and duplicate_status == 409
                and "already applied" in duplicate.get("error", "")
                and detail_status == 200
                and detail["task"]["selected_candidate_id"] == candidate_id
                and compare_status == 200
                and compare["right"]["edit"]["review_task"]["task_id"] == task_id
                and export_status == 200
                and project_export["review_tasks"][0]["task_id"] == task_id
                and project_export["versions"][1]["edit"]["review_task"]["task_id"] == task_id
                and final_status == 200
                and final_data["project"]["final_version_id"] == child_version
                and final_export_status == 200
                and final_export["final_export"]["edit"]["review_task"]["task_id"] == task_id
                and metadata["edit_source"] == "review_task_candidate"
                and metadata["review_task"]["audition_id"] == audition_id
                and needs_status == 201
                and needs["task"]["status"] == "needs_more_work"
                and needs["follow_up_task"]["parent_version_id"] == child_version
                and follow_status == 200
                and follow["task"]["source"]["previous_task_id"] == task_id
                and "sk-secret-value" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"task={task_id}, candidate={candidate_id}, version={child_version}, candidates={len(candidates_data['candidates'])}, follow_up={follow_up_id}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v29_provider_review_candidates_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            provider_status, provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v2.9 Provider Review Candidates Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v2.9 Provider Review Candidates Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "provider review candidates",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Provider review task patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 96}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            audition_status, audition = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]},
            )
            audition_id = audition["audition"]["audition_id"]
            review_status, _review = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                {"rating": 4, "status": "needs_fix", "favorite": True, "notes": r"bass 太满, provider should suggest candidates api_key=sk-secret-value C:\Users\demo\song.wav", "tags": ["provider-review"]},
            )
            marker_status, _marker = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                {"beat": 1, "kind": "fix", "label": "fix provider candidate target"},
            )
            task_status, task_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-task",
                {},
            )
            task_id = task_data["task"]["task_id"]
            local_status, local_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {"strategies": ["balanced"], "render_midi": True})
            provider_candidates_status, provider_candidates = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-tasks/{task_id}/provider-candidates",
                {"candidate_count": 3, "render_midi": True},
            )
            provider_ready = [candidate for candidate in provider_candidates.get("candidates", []) if candidate.get("candidate_type") == "provider_review_patch" and candidate.get("status") == "ready"]
            provider_candidate = provider_ready[0]
            provider_candidate_id = provider_candidate["candidate_id"]
            midi_status, midi = _release_http_bytes(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{provider_candidate_id}/midi")
            report_status, report = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/decision-report")
            refresh_status, refreshed = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/decision-report/refresh", {"note": "release-check v2.9"})
            candidate_json = base / ".musicforge" / "projects" / project_id / "review-tasks" / task_id / "candidates" / provider_candidate_id / "candidate.json"
            original_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data["artifacts"]["midi_path"] = f"review-tasks/{task_id}/candidates/revcand-999/renders/song.mid"
            candidate_json.write_text(json.dumps(polluted_candidate_data), encoding="utf-8")
            polluted_midi_status, polluted_midi = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{provider_candidate_id}/midi")
            candidate_json.write_text(json.dumps(original_candidate_data), encoding="utf-8")
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{provider_candidate_id}/apply",
                {"version_name": "Provider Review Candidate Child", "version_note": "v2.9 provider review candidate smoke"},
            )
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            usage_status, usage = _release_http_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"provider_candidates": provider_candidates, "report": report, "metadata": metadata, "compare": compare, "export": project_export, "final": final_export}, ensure_ascii=False)
            ok = (
                provider_status == 200
                and provider.get("configured") is True
                and created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and audition_status == 201
                and review_status == 200
                and marker_status == 201
                and task_status == 201
                and local_status == 201
                and len(local_data["candidates"]) >= 1
                and provider_candidates_status == 201
                and len(provider_ready) >= 2
                and provider_candidates["decision_report"]["requires_manual_apply"] is True
                and provider_candidates["provider_summary"]["provider_candidate_count"] >= 2
                and midi_status == 200
                and midi.startswith(b"MThd")
                and report_status == 200
                and report["decision_report"]["source_breakdown"]["local_candidate_count"] >= 1
                and report["decision_report"]["source_breakdown"]["provider_candidate_count"] >= 2
                and refresh_status == 200
                and refreshed["decision_report"]["notes"] == "release-check v2.9"
                and polluted_midi_status == 409
                and "unsafe" in polluted_midi.get("error", "")
                and apply_status == 202
                and applied["candidate"]["candidate_type"] == "provider_review_patch"
                and edit_job["status"] == "completed"
                and metadata["review_candidate"]["candidate_type"] == "provider_review_patch"
                and metadata["review_candidate_source"]["provider"] is True
                and metadata["review_provider_patch"]["operation_count"] >= 1
                and metadata["review_decision"]["requires_manual_apply"] is True
                and compare_status == 200
                and compare["right"]["edit"]["review_candidate"]["candidate_type"] == "provider_review_patch"
                and compare["right"]["edit"]["review_decision"]["requires_manual_apply"] is True
                and export_status == 200
                and project_export["review_tasks"][0]["provider_summary"]["provider_candidate_count"] >= 2
                and project_export["versions"][1]["edit"]["review_provider_patch"]["operation_count"] >= 1
                and final_status == 200
                and final_data["project"]["final_version_id"] == child_version
                and final_export_status == 200
                and final_export["final_export"]["edit"]["review_provider_patch"]["operation_count"] >= 1
                and usage_status == 200
                and any(item.get("operation") == "provider_review_candidates" for item in usage.get("records", []))
                and "sk-secret-value" not in serialized
                and "api_key" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"task={task_id}, provider_candidate={provider_candidate_id}, version={child_version}, provider_candidates={len(provider_ready)}, recommended={report.get('decision_report', {}).get('recommended_candidate_id')}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v30_review_sprint_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            provider_status, provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.0 Review Sprint Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v3.0 Review Sprint Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "review sprint",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "Review sprint patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 97}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            task_ids = []
            audition_ids = []
            for index, note in enumerate((r"bass too dense api_key=sk-secret-value C:\Users\demo\song.wav", "bass needs more movement"), start=1):
                audition_status, audition = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                    {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]},
                )
                audition_id = audition["audition"]["audition_id"]
                audition_ids.append(audition_id)
                review_status, _review = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                    {"rating": 4, "status": "needs_fix", "favorite": True, "notes": note, "tags": ["review-sprint"]},
                )
                marker_status, _marker = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                    {"beat": float(index), "kind": "fix", "label": f"fix sprint target {index}"},
                )
                task_status, task_data = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-task",
                    {},
                )
                if not (audition_status == 201 and review_status == 200 and marker_status == 201 and task_status == 201):
                    return False, f"task setup failed: audition={audition_status}, review={review_status}, marker={marker_status}, task={task_status}"
                task_ids.append(task_data["task"]["task_id"])
            sprint_status, sprint_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-sprints",
                {
                    "name": r"Release Sprint C:\Users\demo token=sk-secret-value",
                    "task_ids": task_ids,
                    "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2},
                },
            )
            sprint_id = sprint_data["sprint"]["sprint_id"]
            detail_status, detail = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
            conflict_status, conflicts = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/conflicts/refresh")
            local_status, local_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-local-candidates", {"strategies": ["balanced"], "render_midi": True})
            provider_candidates_status, provider_candidates = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-provider-candidates", {"candidate_count": 2, "render_midi": True})
            provider_ready = [
                candidate
                for item in provider_candidates.get("tasks", [])
                if item.get("task", {}).get("task_id") == task_ids[0]
                for candidate in item.get("candidates", [])
                if candidate.get("candidate_type") == "provider_review_patch" and candidate.get("status") == "ready"
            ]
            provider_candidate_id = provider_ready[0]["candidate_id"]
            midi_status, midi = _release_http_bytes(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/midi")
            candidate_json = base / ".musicforge" / "projects" / project_id / "review-tasks" / task_ids[0] / "candidates" / provider_candidate_id / "candidate.json"
            original_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data = json.loads(candidate_json.read_text(encoding="utf-8"))
            polluted_candidate_data["artifacts"]["midi_path"] = f"review-tasks/{task_ids[0]}/candidates/revcand-999/renders/song.mid"
            candidate_json.write_text(json.dumps(polluted_candidate_data), encoding="utf-8")
            polluted_midi_status, polluted_midi = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/midi")
            candidate_json.write_text(json.dumps(original_candidate_data), encoding="utf-8")
            apply_status, applied = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/apply",
                {"version_name": "Review Sprint Candidate Child", "version_note": "v3.0 review sprint smoke"},
            )
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            refresh_status, refreshed = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/refresh")
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            close_block_status, close_block = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close")
            close_status, closed = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {"force": True, "override_reason": "release-check v3.0 compatibility force close"})
            usage_status, usage = _release_http_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps({"sprint": sprint_data, "provider_candidates": provider_candidates, "metadata": metadata, "compare": compare, "export": project_export, "final": final_export}, ensure_ascii=False)
            conflict_kinds = {item.get("kind") for item in (conflicts.get("conflict_report") or {}).get("conflicts", [])}
            ok = (
                provider_status == 200
                and provider.get("configured") is True
                and created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and len(task_ids) == 2
                and sprint_status == 201
                and detail_status == 200
                and len(detail.get("tasks", [])) == 2
                and conflict_status == 200
                and {"same_section_track", "nearby_markers"} & conflict_kinds
                and local_status == 202
                and local_data.get("created_count", 0) >= 2
                and provider_candidates_status == 202
                and provider_candidates.get("created_count", 0) >= 4
                and provider_candidates["summary"]["counts"]["provider_candidate_count"] >= 4
                and midi_status == 200
                and midi.startswith(b"MThd")
                and polluted_midi_status == 409
                and "unsafe" in polluted_midi.get("error", "")
                and apply_status == 202
                and applied["candidate"]["candidate_type"] == "provider_review_patch"
                and edit_job["status"] == "completed"
                and refresh_status == 200
                and refreshed["summary"]["counts"]["applied"] == 1
                and metadata["review_sprint"]["primary"]["sprint_id"] == sprint_id
                and compare_status == 200
                and compare["right"]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
                and export_status == 200
                and project_export["review_sprints"][0]["sprint_id"] == sprint_id
                and project_export["versions"][1]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
                and final_status == 200
                and final_data["project"]["final_version_id"] == child_version
                and final_export_status == 200
                and final_export["final_export"]["edit"]["review_sprint"]["primary"]["sprint_id"] == sprint_id
                and final_export["final_export"]["review_sprint_summary"]["latest_sprint_id"] == sprint_id
                and close_block_status == 409
                and "closeout gate failed" in close_block.get("error", "")
                and close_status == 200
                and closed["sprint"]["status"] == "closed"
                and closed.get("signoff_summary", {}).get("status") == "signed"
                and usage_status == 200
                and any(item.get("operation") == "review_sprint_provider_candidates" for item in usage.get("records", []))
                and "sk-secret-value" not in serialized
                and "api_key" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"sprint={sprint_id}, tasks={len(task_ids)}, provider_candidate={provider_candidate_id}, version={child_version}, conflicts={sorted(conflict_kinds)}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v31_review_sprint_recommendations_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            provider_status, _provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
            asset_status, asset = _release_http_json(
                server,
                "POST",
                "/api/assets",
                {
                    "asset_type": "bass_pattern",
                    "name": "Release v3.1 bass helper",
                    "tags": ["bass", "arrangement"],
                    "style": "synth pop",
                    "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
                },
            )
            reference_status, reference = _release_http_json(
                server,
                "POST",
                "/api/references/import",
                {
                    "reference_type": "style_note",
                    "filename": "bass.md",
                    "title": "Release v3.1 bass arrangement reference",
                    "tags": ["bass"],
                    "content_base64": "YmFzcyBhcnJhbmdlbWVudCBjb250ZXh0",
                },
            )
            index_status, _index = _release_http_json(server, "POST", "/api/library/rebuild", {})
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.1 Review Sprint Recommendations Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v3.1 Review Sprint Recommendations Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "review sprint recommendations",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "v3.1 recommendation patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 96}}],
                    },
                    "render_midi": True,
                },
            )
            preview = preview_data["preview"]
            task_ids = []
            for index, note in enumerate((r"bass arrangement too dense api_key=sk-secret-value C:\Users\demo\song.wav", "bass arrangement needs more lift"), start=1):
                audition_status, audition = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions",
                    {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]},
                )
                audition_id = audition["audition"]["audition_id"]
                review_status, _review = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review",
                    {"rating": 4, "status": "needs_fix", "favorite": True, "notes": note, "tags": ["review-sprint-recommendations"]},
                )
                marker_status, _marker = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/markers",
                    {"beat": float(index), "kind": "fix", "label": f"recommendation target {index}"},
                )
                task_status, task_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview['preview_id']}/auditions/{audition_id}/review-task", {})
                if not (audition_status == 201 and review_status == 200 and marker_status == 201 and task_status == 201):
                    return False, f"task setup failed: audition={audition_status}, review={review_status}, marker={marker_status}, task={task_status}"
                task_ids.append(task_data["task"]["task_id"])
            sprint_status, sprint_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-sprints",
                {"name": "Release v3.1 Recommendation Sprint", "task_ids": task_ids, "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2}},
            )
            sprint_id = sprint_data["sprint"]["sprint_id"]
            detail_before_status, detail_before = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
            recommendation_get_status, recommendation_get = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations")
            recommendation_refresh_status, recommendation_refresh = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
            report_path = base / ".musicforge" / "projects" / project_id / "review-sprints" / sprint_id / "recommendation-report.json"
            pack_status, pack_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/{task_ids[0]}/context-pack", {"name": "Release v3.1 Recommendation Context"})
            pack_id = pack_data.get("context_pack", {}).get("pack_id")
            pack_apply_status, applied_pack = _release_http_json(server, "POST", f"/api/context-packs/{pack_id}/apply-preview", {})
            detail_after_status, detail_after = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}")
            asset_json = base / ".musicforge" / "assets" / asset["asset"]["asset_id"] / "asset.json"
            original_asset = json.loads(asset_json.read_text(encoding="utf-8"))
            polluted_asset = json.loads(asset_json.read_text(encoding="utf-8"))
            polluted_asset["hidden"] = True
            asset_json.write_text(json.dumps(polluted_asset), encoding="utf-8")
            stale_pack_status, stale_pack = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/{task_ids[0]}/context-pack", {"name": "Stale Recommendation Context"})
            asset_json.write_text(json.dumps(original_asset), encoding="utf-8")
            local_status, local_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-local-candidates", {"strategies": ["balanced"], "render_midi": True})
            provider_status_code, provider_candidates = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/generate-provider-candidates", {"candidate_count": 2, "render_midi": True, "context_pack_id": pack_id})
            recommendation_apply_status, recommendation_apply = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
            provider_ready = [
                candidate
                for item in provider_candidates.get("tasks", [])
                if item.get("task", {}).get("task_id") == task_ids[0]
                for candidate in item.get("candidates", [])
                if candidate.get("candidate_type") == "provider_review_patch" and candidate.get("status") == "ready"
            ]
            provider_candidate_id = provider_ready[0]["candidate_id"]
            apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/apply", {"version_name": "Review Sprint Recommendation Candidate"})
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, _final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps(
                {
                    "recommendation": recommendation_refresh,
                    "pack": pack_data,
                    "metadata": metadata,
                    "compare": compare,
                    "export": project_export,
                    "final": final_export,
                    "stale": stale_pack,
                },
                ensure_ascii=False,
            )
            before_candidates = sum(len(item.get("candidates", [])) for item in detail_before.get("tasks", []))
            after_candidates = sum(len(item.get("candidates", [])) for item in detail_after.get("tasks", []))
            recommendation_summary = recommendation_refresh.get("summary", {})
            ok = (
                provider_status == 200
                and asset_status == 201
                and reference_status == 201
                and index_status == 200
                and created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and sprint_status == 201
                and detail_before_status == 200
                and before_candidates == 0
                and recommendation_get_status == 200
                and recommendation_get["recommendation_report"]["recommended_order"]
                and recommendation_refresh_status == 200
                and recommendation_summary["top_recommendation"]["task_id"] in task_ids
                and recommendation_summary["context_recommendation_count"] >= 1
                and report_path.exists()
                and pack_status == 201
                and pack_data["context_pack"]["created_from"]["source_type"] == "review_sprint_recommendation"
                and pack_apply_status == 200
                and applied_pack["asset_refs"][0]["asset_id"] == asset["asset"]["asset_id"]
                and applied_pack["reference_refs"][0]["reference_id"] == reference["reference"]["reference_id"]
                and detail_after_status == 200
                and after_candidates == 0
                and stale_pack_status == 409
                and "stale" in stale_pack.get("error", "")
                and local_status == 202
                and local_data.get("created_count", 0) >= 2
                and provider_status_code == 202
                and provider_candidates.get("created_count", 0) >= 2
                and recommendation_apply_status == 200
                and recommendation_apply["summary"]["top_recommendation"]["task_id"] in task_ids
                and apply_status == 202
                and edit_job["status"] == "completed"
                and metadata["review_sprint_recommendation"]["primary"]["task_id"] == task_ids[0]
                and compare_status == 200
                and compare["right"]["edit"]["review_sprint_recommendation"]["primary"]["task_id"] == task_ids[0]
                and export_status == 200
                and project_export["review_sprints"][0]["recommendation_summary"]["top_recommendation"]["task_id"] in task_ids
                and project_export["versions"][1]["edit"]["review_sprint_recommendation"]["primary"]["task_id"] == task_ids[0]
                and final_status == 200
                and final_export_status == 200
                and final_export["final_export"]["review_sprint_recommendations"]["latest_sprint_id"] == sprint_id
                and final_export["final_export"]["edit"]["review_sprint_recommendation"]["primary"]["task_id"] == task_ids[0]
                and "sk-secret-value" not in serialized
                and "api_key" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"sprint={sprint_id}, recommended={len(recommendation_refresh.get('recommendation_report', {}).get('recommended_order', []))}, pack={pack_id}, version={child_version}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v32_review_sprint_action_queue_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            provider_status, provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
            asset_status, asset = _release_http_json(
                server,
                "POST",
                "/api/assets",
                {
                    "asset_type": "bass_pattern",
                    "name": "Release v3.2 action queue bass",
                    "tags": ["bass", "arrangement"],
                    "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
                },
            )
            reference_status, reference = _release_http_json(
                server,
                "POST",
                "/api/references/import",
                {
                    "reference_type": "style_note",
                    "filename": "bass.md",
                    "title": "Release v3.2 bass arrangement reference",
                    "tags": ["bass"],
                    "content_base64": "YmFzcyBhcnJhbmdlbWVudCBjb250ZXh0",
                },
            )
            index_status, _index = _release_http_json(server, "POST", "/api/library/rebuild", {})
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.2 Action Queue Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {
                    "name": "Parent",
                    "request": {
                        "title": "Release v3.2 Action Queue Smoke",
                        "language": "English",
                        "style": "synth pop",
                        "theme": "review sprint action queue",
                        "tempo_bpm": 120,
                        "key": "C",
                    },
                },
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {
                    "patch": {
                        "schema_version": 1,
                        "base_plan_hash": state["base_plan_hash"],
                        "label": "v3.2 action queue patch",
                        "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 97}}],
                    },
                    "render_midi": True,
                },
            )
            preview_id = preview_data["preview"]["preview_id"]
            task_ids: list[str] = []
            for index, notes in enumerate((r"bass arrangement too dense api_key=sk-secret-value C:\Users\demo\song.wav", "bass arrangement needs lift"), start=1):
                audition_status, audition = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
                    {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]},
                )
                audition_id = audition["audition"]["audition_id"]
                review_status, _review = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review",
                    {"rating": 4, "status": "needs_fix", "favorite": True, "notes": notes, "tags": ["review-sprint-action-queue"]},
                )
                marker_status, _marker = _release_http_json(
                    server,
                    "POST",
                    f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
                    {"beat": float(index), "kind": "fix", "label": f"queue target {index}"},
                )
                task_status, task_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task", {})
                if not (audition_status == 201 and review_status == 200 and marker_status == 201 and task_status == 201):
                    return False, f"task setup failed: audition={audition_status}, review={review_status}, marker={marker_status}, task={task_status}"
                task_ids.append(task_data["task"]["task_id"])
            sprint_status, sprint_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/review-sprints",
                {"name": "Release v3.2 Action Queue Sprint", "task_ids": task_ids, "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2}},
            )
            sprint_id = sprint_data["sprint"]["sprint_id"]
            queue_status, queue_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            queue = queue_data["queue"]
            queue_id = queue["queue_id"]
            context_item_id = _release_item_id(queue, "save_recommended_context_pack")
            local_item_id = _release_item_id(queue, "generate_local_candidates")
            local_run_status, local_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [context_item_id, local_item_id]})
            task_after_local_status, task_after_local = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}")
            recommendation_status, recommendation = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
            provider_queue_status, provider_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": False})
            provider_queue_id = provider_queue["queue"]["queue_id"]
            provider_item_id = _release_item_id(provider_queue["queue"], "generate_provider_candidates")
            provider_default_status, provider_default = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": [provider_item_id]})
            provider_run_status, provider_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": [provider_item_id], "include_provider": True})
            decision_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / task_ids[0] / "decision-report.json"
            if decision_path.exists():
                decision_path.unlink()
            decision_queue_status, decision_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            decision_item_id = _release_item_id(decision_queue["queue"], "refresh_decision_report")
            decision_run_status, decision_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{decision_queue['queue']['queue_id']}/run", {"item_ids": [decision_item_id]})
            manual_queue_status, manual_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            manual_items = [item for item in manual_queue["queue"].get("items", []) if item.get("action") == "manual_apply_candidate"]
            provider_candidate_id = provider_run["results"][0]["result"]["created_candidate_ids"][0]
            apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/apply", {"version_name": "Action Queue Candidate Child"})
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, _final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            stale_queue_status, stale_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            stale_local_item_id = _release_item_id(stale_queue["queue"], "generate_local_candidates", required=False)
            if not stale_local_item_id:
                stale_local_item_id = stale_queue["queue"]["items"][0]["item_id"]
            report_path = base / ".musicforge" / "projects" / project_id / "review-sprints" / sprint_id / "recommendation-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["created_at"] = "2026-05-14T01:00:00+00:00"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            stale_run_status, stale_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{stale_queue['queue']['queue_id']}/run", {"item_ids": [stale_local_item_id]})
            context_stale_queue_status, context_stale_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            context_stale_item_id = _release_item_id(context_stale_queue["queue"], "save_recommended_context_pack")
            asset_json = base / ".musicforge" / "assets" / asset["asset"]["asset_id"] / "asset.json"
            original_asset = json.loads(asset_json.read_text(encoding="utf-8"))
            polluted_asset = dict(original_asset)
            polluted_asset["hidden"] = True
            asset_json.write_text(json.dumps(polluted_asset), encoding="utf-8")
            context_stale_run_status, context_stale_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{context_stale_queue['queue']['queue_id']}/run", {"item_ids": [context_stale_item_id]})
            asset_json.write_text(json.dumps(original_asset), encoding="utf-8")
            usage_status, usage = _release_http_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
            metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            serialized = json.dumps(
                {
                    "queue": queue_data,
                    "local": local_run,
                    "provider": provider_run,
                    "decision": decision_run,
                    "manual": manual_queue,
                    "metadata": metadata,
                    "compare": compare,
                    "export": project_export,
                    "final": final_export,
                    "stale": stale_run,
                    "context_stale": context_stale_run,
                    "usage": usage,
                },
                ensure_ascii=False,
            )
            ok = (
                provider_status == 200
                and provider.get("configured") is True
                and asset_status == 201
                and reference_status == 201
                and index_status == 200
                and created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and len(task_ids) == 2
                and sprint_status == 201
                and queue_status == 201
                and any(item.get("action") == "save_recommended_context_pack" for item in queue.get("items", []))
                and any(item.get("action") == "generate_local_candidates" for item in queue.get("items", []))
                and local_run_status == 200
                and any(result.get("result", {}).get("context_pack_id") for result in local_run.get("results", []))
                and any(result.get("result", {}).get("created_count", 0) >= 1 for result in local_run.get("results", []))
                and task_after_local_status == 200
                and task_after_local["task"]["status"] == "candidate_ready"
                and recommendation_status == 200
                and recommendation["summary"]["top_recommendation"]["action"] in {"generate_provider", "refresh_decision_report", "apply_ready_candidate"}
                and provider_queue_status == 201
                and provider_default_status == 200
                and provider_default["results"][0]["status"] == "skipped"
                and provider_default["queue"]["status"] == "pending"
                and _release_item(provider_default["queue"], provider_item_id)["status"] == "pending"
                and provider_run_status == 200
                and provider_run["results"][0]["status"] == "completed"
                and provider_run["results"][0]["result"]["created_count"] >= 1
                and decision_queue_status == 201
                and decision_run_status == 200
                and decision_run["results"][0]["status"] == "completed"
                and decision_run["results"][0]["result"]["decision_report"]["requires_manual_apply"] is True
                and manual_queue_status == 201
                and manual_items
                and manual_items[0]["status"] == "manual_required"
                and apply_status == 202
                and edit_job["status"] == "completed"
                and metadata["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
                and compare_status == 200
                and compare["right"]["edit"]["review_sprint_action_queue"]["primary"]["queue_id"]
                and export_status == 200
                and project_export["review_sprints"][0]["action_queue_summary"]["queue_count"] >= 1
                and project_export["versions"][1]["edit"]["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
                and final_status == 200
                and final_export_status == 200
                and final_export["final_export"]["review_sprint_action_queues"]["latest_sprint_id"] == sprint_id
                and final_export["final_export"]["edit"]["review_sprint_action_queue"]["primary"]["sprint_id"] == sprint_id
                and stale_queue_status == 201
                and stale_run_status == 200
                and stale_run["results"][0]["status"] == "blocked"
                and "Recommendation Report changed" in stale_run["results"][0]["error"]
                and context_stale_queue_status == 201
                and context_stale_run_status == 200
                and context_stale_run["results"][0]["status"] == "blocked"
                and "stale" in context_stale_run["results"][0]["error"]
                and usage_status == 200
                and any(item.get("operation") == "review_sprint_action_provider_candidates" for item in usage.get("records", []))
                and "sk-secret-value" not in serialized
                and "api_key" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"sprint={sprint_id}, queue={queue_id}, provider_candidate={provider_candidate_id}, version={child_version}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v33_review_sprint_dashboard_metrics_smoke(root: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old_cwd = Path.cwd()
        server = None
        try:
            os.chdir(base)
            from song_agent.server import create_server

            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            provider_status, provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
            asset_status, _asset = _release_http_json(
                server,
                "POST",
                "/api/assets",
                {"asset_type": "bass_pattern", "name": "Release v3.3 dashboard bass", "tags": ["bass"], "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]}},
            )
            reference_status, _reference = _release_http_json(
                server,
                "POST",
                "/api/references/import",
                {"reference_type": "style_note", "filename": "metrics.md", "title": "Release v3.3 metrics reference", "tags": ["metrics"], "content_base64": "bWV0cmljcyByZWZlcmVuY2U="},
            )
            index_status, _index = _release_http_json(server, "POST", "/api/library/rebuild", {})
            created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.3 Metrics Smoke"})
            project_id = created["project"]["project_id"]
            version_status, version = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions",
                {"name": "Parent", "request": {"title": "Release v3.3 Metrics Smoke", "language": "English", "style": "synth pop", "theme": "dashboard metrics", "tempo_bpm": 118, "key": "C"}},
            )
            parent_job = _release_wait_http_job(server, version["job"]["job_id"])
            state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
            note_id = state["tracks"][0]["notes"][0]["note_id"]
            preview_status, preview_data = _release_http_json(
                server,
                "POST",
                f"/api/projects/{project_id}/versions/v001/editor-preview",
                {"patch": {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "label": "v3.3 metrics patch", "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 96}}]}, "render_midi": True},
            )
            preview_id = preview_data["preview"]["preview_id"]
            task_ids: list[str] = []
            for index, notes in enumerate((r"metrics bass too dense api_key=sk-secret-value C:\Users\demo\song.wav", "metrics chorus needs lift"), start=1):
                audition_status, audition = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions", {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]})
                audition_id = audition["audition"]["audition_id"]
                review_status, _review = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review", {"rating": 4, "status": "needs_fix", "notes": notes, "tags": ["metrics"]})
                marker_status, _marker = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers", {"beat": float(index), "kind": "fix", "label": f"metrics target {index}"})
                task_status, task_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task", {})
                if not (audition_status == 201 and review_status == 200 and marker_status == 201 and task_status == 201):
                    return False, f"task setup failed: audition={audition_status}, review={review_status}, marker={marker_status}, task={task_status}"
                task_ids.append(task_data["task"]["task_id"])
            sprint_status, sprint_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"name": "Release v3.3 Metrics Sprint", "task_ids": task_ids, "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2}})
            sprint_id = sprint_data["sprint"]["sprint_id"]
            recommendation_status, _recommendation = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/recommendations/refresh", {})
            queue_status, queue_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": False})
            queue_id = queue_data["queue"]["queue_id"]
            context_item_id = _release_item_id(queue_data["queue"], "save_recommended_context_pack")
            local_item_id = _release_item_id(queue_data["queue"], "generate_local_candidates")
            local_run_status, local_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [context_item_id, local_item_id]})
            provider_queue_status, provider_queue = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
            provider_queue_id = provider_queue["queue"]["queue_id"]
            provider_item_id = _release_item_id(provider_queue["queue"], "generate_provider_candidates")
            provider_run_status, provider_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{provider_queue_id}/run", {"item_ids": [provider_item_id], "include_provider": True})
            provider_candidate_id = provider_run["results"][0]["result"]["created_candidate_ids"][0]
            decision_status, decision = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/decision-report/refresh", {})
            apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_ids[0]}/candidates/{provider_candidate_id}/apply", {"version_name": "Metrics Candidate Child"})
            edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
            child_version = applied["version"]["version_id"]
            sprint_metrics_status, sprint_metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh")
            second_sprint_status, second_sprint = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"name": "Release v3.3 Latest Metrics Sprint", "task_ids": [task_ids[1]], "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 1}})
            second_sprint_id = second_sprint.get("sprint", {}).get("sprint_id")
            second_metrics_status, second_metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{second_sprint_id}/metrics/refresh")
            project_metrics_status, project_metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-metrics/refresh")
            export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
            final_status, _final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
            final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
            metrics_report = sprint_metrics.get("metrics_report", {})
            second_metrics_report = second_metrics.get("metrics_report", {})
            project_report = project_metrics.get("review_metrics", {})
            final_review_metrics = final_export.get("final_export", {}).get("review_metrics", {})
            serialized = json.dumps({"sprint_metrics": sprint_metrics, "project_metrics": project_metrics, "export": project_export, "final": final_export}, ensure_ascii=False)
            allowed_quality = {"improved", "unchanged", "regressed", "not_available"}
            allowed_readiness = {"ready_to_close", "needs_review", "needs_candidates", "blocked", "stale", "no_data"}
            expected_completion_rate = second_metrics.get("summary", {}).get("completion_rate")
            expected_quality_delta = second_metrics.get("summary", {}).get("quality_delta")
            expected_warnings = second_metrics.get("summary", {}).get("warnings", [])
            ok = (
                provider_status == 200
                and provider.get("configured") is True
                and asset_status == 201
                and reference_status == 201
                and index_status == 200
                and created_status == 201
                and version_status == 202
                and parent_job["status"] == "completed"
                and state_status == 200
                and preview_status == 201
                and len(task_ids) == 2
                and sprint_status == 201
                and recommendation_status == 200
                and queue_status == 201
                and local_run_status == 200
                and any(result.get("result", {}).get("context_pack_id") for result in local_run.get("results", []))
                and any(result.get("result", {}).get("created_count", 0) >= 1 for result in local_run.get("results", []))
                and provider_queue_status == 201
                and provider_run_status == 200
                and provider_run["results"][0]["result"]["created_count"] >= 1
                and decision_status == 200
                and decision["decision_report"]["requires_manual_apply"] is True
                and apply_status == 202
                and edit_job["status"] == "completed"
                and sprint_metrics_status == 200
                and second_sprint_status == 201
                and second_metrics_status == 200
                and metrics_report.get("overview", {}).get("task_count", 0) >= 1
                and metrics_report.get("candidate_funnel", {}).get("candidate_count", 0) >= 1
                and metrics_report.get("candidate_funnel", {}).get("provider_candidate_count", 0) >= 1
                and metrics_report.get("action_queue_execution", {}).get("completed_action_count", 0) >= 1
                and metrics_report.get("provider_usage", {}).get("provider_call_count", 0) >= 1
                and metrics_report.get("manual_decisions", {}).get("manual_apply_count", 0) >= 1
                and metrics_report.get("quality_delta", {}).get("status") in allowed_quality
                and metrics_report.get("risk_readiness", {}).get("readiness") in allowed_readiness
                and second_metrics_report.get("risk_readiness", {}).get("readiness") in allowed_readiness
                and project_metrics_status == 200
                and project_report.get("latest_sprint_id") == second_sprint_id
                and project_report.get("latest_readiness") in allowed_readiness
                and export_status == 200
                and any(item.get("metrics_summary", {}).get("sprint_id") == sprint_id for item in project_export.get("review_sprints", []))
                and any(item.get("metrics_summary", {}).get("sprint_id") == second_sprint_id for item in project_export.get("review_sprints", []))
                and project_export["review_metrics_summary"]["latest_sprint_id"] == second_sprint_id
                and final_status == 200
                and final_export_status == 200
                and final_review_metrics.get("latest_sprint_id") == second_sprint_id
                and final_review_metrics.get("completion_rate") == expected_completion_rate
                and final_review_metrics.get("quality_delta") == expected_quality_delta
                and final_review_metrics.get("warnings", []) == expected_warnings
                and "sk-secret-value" not in serialized
                and "api_key" not in serialized
                and "C:\\Users" not in serialized
                and str(base) not in serialized
            )
            return ok, f"sprint={sprint_id}, latest={second_sprint_id}, readiness={metrics_report.get('risk_readiness', {}).get('readiness')}, version={child_version}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            os.chdir(old_cwd)


def _v34_provider_review_judge_smoke(root: Path) -> tuple[bool, str]:
    base = root / ".release-check" / "v34-provider-review-judge"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        provider_status, provider = _release_http_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-review", "api_key": "sk-secret-value"})
        created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.4 Judge Smoke"})
        project_id = created["project"]["project_id"]
        version_status, version = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"name": "Parent", "request": {"title": "Release v3.4 Judge Smoke", "language": "English", "style": "synth pop", "theme": "provider judge", "tempo_bpm": 118, "key": "C"}},
        )
        parent_job = _release_wait_http_job(server, version["job"]["job_id"])
        state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        note_id = state["tracks"][0]["notes"][0]["note_id"]
        preview_status, preview_data = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {"patch": {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "label": "v3.4 judge patch", "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 94}}]}, "render_midi": True},
        )
        preview_id = preview_data["preview"]["preview_id"]
        audition_status, audition = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions", {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]})
        audition_id = audition["audition"]["audition_id"]
        review_status, _review = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review", {"rating": 4, "status": "needs_fix", "notes": r"judge bass needs lift api_key=sk-secret-value C:\Users\demo\song.wav", "tags": ["judge"]})
        marker_status, _marker = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers", {"beat": 18.0, "kind": "fix", "label": "judge target"})
        task_status, task_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task", {})
        task_id = task_data["task"]["task_id"]
        local_status, local = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {"strategies": ["balanced", "bold"], "render_midi": True})
        provider_candidates_status, provider_candidates = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/provider-candidates", {"candidate_count": 2, "template_id": "provider-review-candidates", "render_midi": True})
        ready_ids = [candidate.get("candidate_id") for candidate in provider_candidates.get("candidates", []) + local.get("candidates", []) if candidate.get("status") == "ready"]
        judge_get_status, judge_get = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/judge-report")
        judge_status, judge = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/judge-report/refresh", {"template_id": "provider-review-judge", "note": r"release judge C:\Users\demo"})
        judge_id = judge.get("judge_report", {}).get("recommended_candidate_id")
        decision_status, decision = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/decision-report/refresh", {})
        sprint_status, sprint_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"name": "Release v3.4 Judge Sprint", "task_ids": [task_id], "settings": {"local_candidate_strategies": ["balanced"], "provider_candidate_count": 2}})
        sprint_id = sprint_data["sprint"]["sprint_id"]
        sprint_judge_status, sprint_judge = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/judge-summary/refresh", {"skip_existing_current": True, "max_tasks": 5})
        queue_status, queue_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues", {"refresh_recommendations": True})
        queue_id = queue_data["queue"]["queue_id"]
        judge_item_id = _release_item_id(queue_data["queue"], "refresh_judge_report")
        queue_default_status, queue_default = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [judge_item_id]})
        queue_run_status, queue_run = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/action-queues/{queue_id}/run", {"item_ids": [judge_item_id], "include_provider": True})
        apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{judge_id}/apply", {"version_name": "Judge Candidate Child"})
        edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
        child_version = applied["version"]["version_id"]
        metadata_path = Path(edit_job["output_dir"]) / "data" / "edit-metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        compare_status, compare = _release_http_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={child_version}")
        metrics_status, metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh")
        project_metrics_status, project_metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-metrics/refresh")
        export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_status, _final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
        usage_status, usage = _release_http_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        serialized = json.dumps(
            {
                "judge": judge,
                "sprint_judge": sprint_judge,
                "queue": queue_run,
                "metadata": metadata,
                "compare": compare,
                "metrics": metrics,
                "project_metrics": project_metrics,
                "export": project_export,
                "final": final_export,
                "usage": usage,
            },
            ensure_ascii=False,
        )
        ok = (
            provider_status == 200
            and provider.get("configured") is True
            and created_status == 201
            and version_status == 202
            and parent_job["status"] == "completed"
            and state_status == 200
            and preview_status == 201
            and audition_status == 201
            and review_status == 200
            and marker_status == 201
            and task_status == 201
            and local_status == 201
            and provider_candidates_status == 201
            and len(ready_ids) >= 2
            and judge_get_status == 200
            and judge_get.get("summary", {}).get("status") == "not_started"
            and judge_status == 200
            and judge_id in ready_ids
            and len(judge.get("judge_report", {}).get("candidate_scores", [])) >= 2
            and decision_status == 200
            and decision.get("decision_report", {}).get("judge_summary", {}).get("recommended_candidate_id") == judge_id
            and decision.get("decision_report", {}).get("requires_manual_apply") is True
            and sprint_status == 201
            and sprint_judge_status == 200
            and sprint_judge.get("judge_summary", {}).get("judged_task_count", 0) >= 1
            and queue_status == 201
            and _release_item(queue_data["queue"], judge_item_id).get("safety") == "provider_safe"
            and queue_default_status == 200
            and queue_default.get("results", [{}])[0].get("status") == "skipped"
            and queue_default.get("queue", {}).get("status") == "pending"
            and queue_run_status == 200
            and queue_run.get("results", [{}])[0].get("status") == "completed"
            and apply_status == 202
            and edit_job["status"] == "completed"
            and metadata.get("review_judge", {}).get("judge_recommended_candidate_id") == judge_id
            and metadata.get("review_judge", {}).get("applied_matches_judge") is True
            and compare_status == 200
            and compare.get("right", {}).get("edit", {}).get("review_judge", {}).get("applied_matches_judge") is True
            and metrics_status == 200
            and metrics.get("metrics_report", {}).get("judge_metrics", {}).get("judged_task_count", 0) >= 1
            and metrics.get("metrics_report", {}).get("judge_metrics", {}).get("judge_provider_tokens", 0) >= 1
            and project_metrics_status == 200
            and project_metrics.get("summary", {}).get("judge_summary", {}).get("judged_task_count", 0) >= 1
            and export_status == 200
            and project_export.get("review_tasks", [{}])[0].get("judge_summary", {}).get("recommended_candidate_id") == judge_id
            and project_export.get("review_sprints", [{}])[0].get("judge_summary", {}).get("judged_task_count", 0) >= 1
            and final_status == 200
            and final_export_status == 200
            and final_export.get("final_export", {}).get("review_judge", {}).get("applied_matches_judge") is True
            and usage_status == 200
            and any(record.get("operation") == "provider_review_judge" for record in usage.get("records", []))
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, f"task={task_id}, sprint={sprint_id}, judge={judge_id}, version={child_version}, tokens={metrics.get('metrics_report', {}).get('judge_metrics', {}).get('judge_provider_tokens')}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v35_review_sprint_closeout_smoke(root: Path) -> tuple[bool, str]:
    base = root / ".release-check" / "v35-review-sprint-closeout"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.5 Closeout Smoke"})
        project_id = created["project"]["project_id"]
        version_status, version = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"name": "Parent", "request": {"title": "Release v3.5 Closeout Smoke", "language": "English", "style": "synth pop", "theme": "closeout", "tempo_bpm": 118, "key": "C"}},
        )
        parent_job = _release_wait_http_job(server, version["job"]["job_id"])
        state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state")
        note_id = state["tracks"][0]["notes"][0]["note_id"]
        preview_status, preview_data = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/editor-preview",
            {"patch": {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "label": "v3.5 closeout patch", "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 95}}]}, "render_midi": True},
        )
        preview_id = preview_data["preview"]["preview_id"]
        audition_status, audition = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions", {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]})
        audition_id = audition["audition"]["audition_id"]
        review_status, _review = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review", {"rating": 4, "status": "needs_fix", "notes": r"closeout bass check api_key=sk-secret-value C:\Users\demo\song.wav", "tags": ["closeout"]})
        marker_status, _marker = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers", {"beat": 1.0, "kind": "fix", "label": "closeout target"})
        task_status, task_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task", {})
        task_id = task_data["task"]["task_id"]
        local_status, local = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {"strategies": ["balanced"], "render_midi": True})
        candidate_id = local["candidates"][0]["candidate_id"]
        unresolved_project_status, unresolved_project = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.5 Missing Delivery Smoke"})
        unresolved_project_id = unresolved_project.get("project", {}).get("project_id")
        unresolved_version_status, unresolved_version = _release_http_json(
            server,
            "POST",
            f"/api/projects/{unresolved_project_id}/versions",
            {"name": "Parent", "request": {"title": "Release v3.5 Missing Delivery Smoke", "language": "English", "style": "synth pop", "theme": "closeout", "tempo_bpm": 118, "key": "C"}},
        )
        unresolved_parent_job = _release_wait_http_job(server, unresolved_version["job"]["job_id"])
        unresolved_state_status, unresolved_state = _release_http_json(server, "GET", f"/api/projects/{unresolved_project_id}/versions/v001/editor-state")
        unresolved_note_id = unresolved_state["tracks"][0]["notes"][0]["note_id"]
        unresolved_preview_status, unresolved_preview = _release_http_json(
            server,
            "POST",
            f"/api/projects/{unresolved_project_id}/versions/v001/editor-preview",
            {"patch": {"schema_version": 1, "base_plan_hash": unresolved_state["base_plan_hash"], "label": "v3.5 unresolved patch", "operations": [{"op": "update_note", "track_id": "track-001", "note_id": unresolved_note_id, "patch": {"velocity": 92}}]}, "render_midi": False},
        )
        unresolved_preview_id = unresolved_preview["preview"]["preview_id"]
        unresolved_audition_status, unresolved_audition = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/editor-previews/{unresolved_preview_id}/auditions", {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]})
        unresolved_audition_id = unresolved_audition["audition"]["audition_id"]
        unresolved_review_status, _unresolved_review = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/editor-previews/{unresolved_preview_id}/auditions/{unresolved_audition_id}/review", {"rating": 4, "status": "needs_fix", "notes": "resolved without delivery version", "tags": ["closeout"]})
        unresolved_marker_status, _unresolved_marker = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/editor-previews/{unresolved_preview_id}/auditions/{unresolved_audition_id}/markers", {"beat": 1.0, "kind": "fix", "label": "closeout target"})
        unresolved_task_status, unresolved_task_data = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/editor-previews/{unresolved_preview_id}/auditions/{unresolved_audition_id}/review-task", {})
        unresolved_task_id = unresolved_task_data["task"]["task_id"]
        unresolved_project_path = base / ".musicforge" / "projects" / unresolved_project_id / "project.json"
        unresolved_project_data = read_json(unresolved_project_path)
        write_json(unresolved_project_path, {**unresolved_project_data, "selected_version_id": None, "final_version_id": None, "latest_version_id": "v001"})
        unresolved_task_path = base / ".musicforge" / "projects" / unresolved_project_id / "review-tasks" / unresolved_task_id / "task.json"
        unresolved_task_data_disk = read_json(unresolved_task_path)
        write_json(unresolved_task_path, {**unresolved_task_data_disk, "status": "resolved", "selected_candidate_id": None, "applied_version_id": None})
        unresolved_sprint_status, unresolved_sprint = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/review-sprints", {"name": "Release v3.5 Missing Delivery Sprint", "task_ids": [unresolved_task_id]})
        unresolved_sprint_id = unresolved_sprint.get("sprint", {}).get("sprint_id")
        unresolved_closeout_status, unresolved_closeout = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/review-sprints/{unresolved_sprint_id}/closeout/refresh")
        unresolved_close_status, unresolved_close = _release_http_json(server, "POST", f"/api/projects/{unresolved_project_id}/review-sprints/{unresolved_sprint_id}/close", {})
        unresolved_missing_check = next((check for check in unresolved_closeout.get("closeout_report", {}).get("checks", []) if isinstance(check, dict) and check.get("check_id") == "missing_applied_version"), {})
        sprint_status, sprint_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"name": "Release v3.5 Closeout Sprint", "task_ids": [task_id]})
        sprint_id = sprint_data["sprint"]["sprint_id"]
        closeout_get_status, closeout_get = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout")
        close_block_status, close_block = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {})
        force_missing_status, force_missing = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {"force": True})
        apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply", {"version_name": "Closeout Candidate Child"})
        edit_job = _release_wait_http_job(server, applied["job"]["job_id"])
        child_version = applied["version"]["version_id"]
        metrics_status, metrics = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh")
        closeout_refresh_status, closeout_refresh = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout/refresh")
        close_status, closed = _release_http_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {"selected_version_id": child_version, "notes": r"accepted C:\Users\demo"})
        signoff_status, signoff = _release_http_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/signoff")
        export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_status, _final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version, "force": True})
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"version_id": child_version, "force": True, "include_audio": False, "include_stems": False, "include_stem_audio": False})
        serialized = json.dumps({"closeout": closeout_refresh, "closed": closed, "signoff": signoff, "export": project_export, "final": final_export}, ensure_ascii=False)
        final_closeout = final_export.get("final_export", {}).get("review_sprint_closeout", {})
        ok = (
            created_status == 201
            and version_status == 202
            and parent_job["status"] == "completed"
            and state_status == 200
            and preview_status == 201
            and audition_status == 201
            and review_status == 200
            and marker_status == 201
            and task_status == 201
            and local_status == 201
            and unresolved_project_status == 201
            and unresolved_version_status == 202
            and unresolved_parent_job["status"] == "completed"
            and unresolved_state_status == 200
            and unresolved_preview_status == 201
            and unresolved_audition_status == 201
            and unresolved_review_status == 200
            and unresolved_marker_status == 201
            and unresolved_task_status == 201
            and unresolved_sprint_status == 201
            and unresolved_closeout_status == 200
            and unresolved_closeout.get("closeout_report", {}).get("recommended_final_version") == {}
            and unresolved_missing_check.get("status") == "failed"
            and unresolved_closeout.get("summary", {}).get("close_allowed") is False
            and unresolved_close_status == 409
            and "closeout gate failed" in unresolved_close.get("error", "")
            and sprint_status == 201
            and closeout_get_status == 200
            and closeout_get.get("summary", {}).get("close_allowed") is False
            and close_block_status == 409
            and "closeout gate failed" in close_block.get("error", "")
            and force_missing_status == 400
            and "override_reason" in force_missing.get("error", "")
            and apply_status == 202
            and edit_job["status"] == "completed"
            and metrics_status == 200
            and metrics.get("summary", {}).get("readiness") == "ready_to_close"
            and closeout_refresh_status == 200
            and closeout_refresh.get("summary", {}).get("close_allowed") is True
            and close_status == 200
            and closed.get("signoff_summary", {}).get("status") == "signed"
            and closed.get("sprint", {}).get("status") == "closed"
            and signoff_status == 200
            and signoff.get("summary", {}).get("selected_version_id") == child_version
            and export_status == 200
            and project_export.get("review_sprints", [{}])[0].get("closeout_summary", {}).get("status") in {"passed", "warning"}
            and project_export.get("review_sprints", [{}])[0].get("signoff_summary", {}).get("status") == "signed"
            and final_status == 200
            and final_export_status == 200
            and final_closeout.get("latest_sprint_id") == sprint_id
            and final_closeout.get("signed_sprint_count") == 1
            and final_closeout.get("selected_version_id") == child_version
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, f"sprint={sprint_id}, closeout={closeout_refresh.get('summary', {}).get('status')}, missing_delivery={unresolved_missing_check.get('status')}, signed={signoff.get('summary', {}).get('status')}, version={child_version}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v36_delivery_qa_handoff_smoke(root: Path) -> tuple[bool, str]:
    base = root / ".release-check" / "v36-delivery-qa-handoff"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": "Release v3.6 Delivery QA Smoke"})
        project_id = created["project"]["project_id"]
        version_status, version = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"name": "Delivery QA Parent", "request": {"title": "Release v3.6 Delivery QA Smoke", "language": "English", "style": "synth pop", "theme": "handoff", "tempo_bpm": 118, "key": "C"}},
        )
        parent_job = _release_wait_http_job(server, version["job"]["job_id"])
        final_status, final_data = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
        export_status, exported = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        missing_zip_status, missing_zip = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        sign_block_status, sign_block = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
        force_missing_status, force_missing = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"force": True})
        zip_status, zipped = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        qa_status, qa = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        sign_status, signed = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "release-check", "notes": r"accepted C:\Users\demo api_key=sk-secret-value"})
        duplicate_status, duplicate = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
        export_after_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_after_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        zip_after_status, zipped_after = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        qa_after_status, qa_after = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        reset_status, reset = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": r"release rebuild C:\Users\demo"})
        zip_path = base / ".musicforge" / "projects" / project_id / "final-export.zip"
        project_dir = base / ".musicforge" / "projects" / project_id
        manifest_path = project_dir / "final-export" / "manifest.json"
        manifest_after_zip = read_json(manifest_path)
        with zipfile.ZipFile(zip_path, "r") as archive:
            zipped_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        zip_path_clean = (
            "path" not in zipped_after.get("zip", {})
            and "path" not in manifest_after_zip.get("zip", {})
            and "path" not in zipped_manifest.get("zip", {})
            and str(project_dir) not in json.dumps({"response": zipped_after, "manifest": manifest_after_zip, "zip_manifest": zipped_manifest}, ensure_ascii=False)
        )
        hidden_manifest = read_json(manifest_path)
        song_mid = project_dir / "final-export" / "song.mid"
        if song_mid.exists():
            song_mid.unlink()
        hidden_manifest["files"] = [item for item in hidden_manifest.get("files", []) if not (isinstance(item, dict) and item.get("path") == "song.mid")]
        write_json(manifest_path, hidden_manifest)
        build_final_export_zip(project_dir, now="2026-05-15T00:02:00+00:00")
        hidden_status, hidden = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        hidden_required_check = next((check for check in hidden.get("delivery_qa", {}).get("checks", []) if isinstance(check, dict) and check.get("check_id") == "required_artifacts_exist"), {})
        hidden_sign_status, hidden_sign = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
        final_after_hidden_status, _final_after_hidden = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        zip_rebuilt_status, _zip_rebuilt = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        polluted_manifest = read_json(manifest_path)
        polluted_manifest.setdefault("zip", {})["path"] = r"C:\Users\demo\Documents\musicforge\final-export.zip"
        write_json(manifest_path, polluted_manifest)
        polluted_manifest_status, polluted_manifest_qa = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        redaction_check = next((check for check in polluted_manifest_qa.get("delivery_qa", {}).get("checks", []) if isinstance(check, dict) and check.get("check_id") == "redaction_scan"), {})
        final_after_redaction_status, _final_after_redaction = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        zip_clean_rebuilt_status, _zip_clean_rebuilt = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        with zipfile.ZipFile(zip_path, "a") as archive:
            archive.writestr("extra.txt", "extra")
        stale_status, stale = _release_http_json(server, "GET", f"/api/projects/{project_id}/delivery-qa")
        polluted_status, polluted = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        polluted_zip_check = next((check for check in polluted.get("delivery_qa", {}).get("checks", []) if isinstance(check, dict) and check.get("check_id") == "zip_manifest_match"), {})
        history_path = base / ".musicforge" / "projects" / project_id / "delivery-signoff-history.jsonl"
        serialized = json.dumps({"signed": signed, "project_export": project_export, "final_export": final_export, "qa_after": qa_after, "reset": reset}, ensure_ascii=False)
        ok = (
            created_status == 201
            and version_status == 202
            and parent_job["status"] == "completed"
            and final_status == 200
            and final_data.get("project", {}).get("final_version_id") == "v001"
            and export_status == 200
            and exported.get("final_export", {}).get("version_id") == "v001"
            and missing_zip_status == 200
            and missing_zip.get("summary", {}).get("handoff_allowed") is False
            and missing_zip.get("summary", {}).get("readiness") == "needs_zip"
            and sign_block_status == 409
            and "Delivery QA gate failed" in sign_block.get("error", "")
            and force_missing_status == 400
            and "override_reason" in force_missing.get("error", "")
            and zip_status == 200
            and zipped.get("zip", {}).get("sha256")
            and qa_status == 200
            and qa.get("summary", {}).get("handoff_allowed") is True
            and sign_status == 200
            and signed.get("summary", {}).get("status") == "signed"
            and duplicate_status == 409
            and "already signed off" in duplicate.get("error", "")
            and export_after_status == 200
            and project_export.get("delivery_qa_summary", {}).get("status") in {"passed", "warning"}
            and project_export.get("delivery_signoff_summary", {}).get("status") == "signed"
            and final_after_status == 200
            and final_export.get("final_export", {}).get("delivery_qa", {}).get("status") in {"passed", "warning"}
            and final_export.get("final_export", {}).get("delivery_signoff", {}).get("status") == "signed"
            and zip_after_status == 200
            and zipped_after.get("zip", {}).get("sha256")
            and qa_after_status == 200
            and qa_after.get("summary", {}).get("handoff_allowed") is True
            and reset_status == 200
            and reset.get("summary", {}).get("status") == "reset"
            and history_path.exists()
            and zip_path_clean
            and hidden_status == 200
            and hidden.get("summary", {}).get("handoff_allowed") is False
            and hidden_required_check.get("status") == "failed"
            and hidden_sign_status == 409
            and "Delivery QA gate failed" in hidden_sign.get("error", "")
            and final_after_hidden_status == 200
            and zip_rebuilt_status == 200
            and polluted_manifest_status == 200
            and polluted_manifest_qa.get("summary", {}).get("handoff_allowed") is False
            and redaction_check.get("status") == "failed"
            and final_after_redaction_status == 200
            and zip_clean_rebuilt_status == 200
            and stale_status == 200
            and stale.get("delivery_qa", {}).get("status") == "stale"
            and polluted_status == 200
            and polluted.get("summary", {}).get("handoff_allowed") is False
            and polluted_zip_check.get("status") == "failed"
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, f"project={project_id}, qa={qa_after.get('summary', {}).get('status')}, sign={signed.get('summary', {}).get('status')}, hidden_core={hidden_required_check.get('status')}, raw_redaction={redaction_check.get('status')}, polluted_zip={polluted_zip_check.get('status')}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v37_release_workspace_smoke(root: Path) -> tuple[bool, str]:
    base = (root / ".release-check" / "v37-release-workspace").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        first_project = _v37_signed_project(server, "Release Workspace Track One")
        second_project = _v37_signed_project(server, "Release Workspace Track Two")
        created_status, created = _release_http_json(
            server,
            "POST",
            "/api/releases",
            {"name": "Release Workspace EP", "release_type": "ep", "primary_artist": "MusicForge", "catalog_id": "MF-370"},
        )
        release_id = created.get("release", {}).get("release_id")
        add_first_status, add_first = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        project_targets_status, project_targets = _release_http_json(server, "GET", f"/api/projects/{second_project}/release-targets")
        add_second_status, add_second = _release_http_json(server, "POST", f"/api/projects/{second_project}/add-to-release", {"release_id": release_id})
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        sign_before_export_status, sign_before_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {})
        export_status, exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, zipped = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        zip_download_status, zip_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/export.zip")
        sign_status, signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "notes": r"accepted C:\Users\demo api_key=sk-secret-value"})
        blocked_add_status, blocked_add = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        reset_missing_status, reset_missing = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {})
        reset_status, reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": r"release rebuild C:\Users\demo"})
        release_dir = base / ".musicforge" / "releases" / release_id
        export_manifest = read_json(release_dir / "release-export" / "manifest.json")
        with zipfile.ZipFile(release_dir / "release-export.zip", "r") as archive:
            zipped_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            zipped_signoff = json.loads(archive.read("release-signoff.json").decode("utf-8"))
            zip_names = archive.namelist()
        manifest_hash = stable_hash({key: value for key, value in export_manifest.items() if key != "zip"})
        export_serialized = json.dumps({"exported": exported, "zipped": zipped, "manifest": export_manifest, "zip_manifest": zipped_manifest}, ensure_ascii=False)
        zip_safe = (
            "path" not in zipped.get("zip", {})
            and "path" not in export_manifest.get("zip", {})
            and "path" not in zipped_manifest.get("zip", {})
            and str(base) not in export_serialized
            and "C:\\Users" not in export_serialized
            and all(not name.startswith("/") and ".." not in Path(name).parts for name in zip_names)
        )

        project_dir = base / ".musicforge" / "projects" / first_project
        manifest_path = project_dir / "final-export" / "manifest.json"
        hidden_manifest = read_json(manifest_path)
        song_mid = project_dir / "final-export" / "song.mid"
        if song_mid.exists():
            song_mid.unlink()
        hidden_manifest["files"] = [item for item in hidden_manifest.get("files", []) if not (isinstance(item, dict) and item.get("path") == "song.mid")]
        write_json(manifest_path, hidden_manifest)
        build_final_export_zip(project_dir, now="2026-05-15T00:05:00+00:00")
        stale_status, stale = _release_http_json(server, "GET", f"/api/releases/{release_id}/qa")
        missing_status, missing = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        missing_core_check = next((check for check in missing.get("release_qa", {}).get("track_checks", []) if isinstance(check, dict) and check.get("check_id") == "final_export_core_files"), {})

        release_json_path = release_dir / "release.json"
        polluted_release = read_json(release_json_path)
        polluted_release.setdefault("metadata", {})["local_path"] = r"C:\Users\demo\release\secret.zip"
        write_json(release_json_path, polluted_release)
        redaction_status, redaction = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        redaction_check = next((check for check in redaction.get("release_qa", {}).get("checks", []) if isinstance(check, dict) and check.get("check_id") == "redaction_scan"), {})
        serialized = json.dumps({"signed": signed, "reset": reset, "project_targets": project_targets}, ensure_ascii=False)
        ok = (
            created_status == 201
            and release_id
            and add_first_status == 200
            and add_first.get("summary", {}).get("track_count") == 1
            and project_targets_status == 200
            and any(item.get("release_id") == release_id for item in project_targets.get("releases", []))
            and add_second_status == 200
            and add_second.get("summary", {}).get("track_count") == 2
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and sign_before_export_status == 409
            and "Release Export" in sign_before_export.get("error", "")
            and export_status == 200
            and exported.get("summary", {}).get("track_count") == 2
            and zip_status == 200
            and zipped.get("zip", {}).get("sha256")
            and zip_download_status == 200
            and zip_bytes.startswith(b"PK")
            and sign_status == 200
            and signed.get("summary", {}).get("status") == "signed"
            and signed.get("signoff", {}).get("export_manifest_hash") == manifest_hash
            and zipped_signoff.get("export_manifest_hash") == manifest_hash
            and stable_hash({key: value for key, value in zipped_manifest.items() if key != "zip"}) == manifest_hash
            and blocked_add_status == 409
            and "signed" in blocked_add.get("error", "").lower()
            and reset_missing_status == 400
            and "reason" in reset_missing.get("error", "")
            and reset_status == 200
            and reset.get("summary", {}).get("status") == "reset"
            and zip_safe
            and stale_status == 200
            and stale.get("release_qa", {}).get("status") == "stale"
            and missing_status == 200
            and missing.get("summary", {}).get("status") == "failed"
            and missing_core_check.get("status") == "failed"
            and redaction_status == 200
            and redaction.get("summary", {}).get("status") == "failed"
            and redaction_check.get("status") == "failed"
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, f"release={release_id}, qa={qa.get('summary', {}).get('status')}, sign={signed.get('summary', {}).get('status')}, missing_core={missing_core_check.get('status')}, raw_redaction={redaction_check.get('status')}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v38_release_zip_verifier_smoke(root: Path) -> tuple[bool, str]:
    base = (root / ".release-check" / "v38-release-verifier").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        first_project = _v37_signed_project(server, "Release Verifier Track One")
        second_project = _v37_signed_project(server, "Release Verifier Track Two")
        created_status, created = _release_http_json(
            server,
            "POST",
            "/api/releases",
            {"name": "Release Verifier EP", "release_type": "ep", "primary_artist": "MusicForge", "catalog_id": "MF-380"},
        )
        release_id = created.get("release", {}).get("release_id")
        add_first_status, _add_first = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        add_second_status, _add_second = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zipped = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})
        zip_path = base / ".musicforge" / "releases" / str(release_id) / "release-export.zip"
        if not zip_path.exists():
            return False, f"zip missing: created={created_status}, add1={add_first_status}, add2={add_second_status}, qa={qa_status}, export={export_status}, zip={zip_status}, sign={sign_status}, export_body={_exported}, zip_body={_zipped}, sign_body={signed}"

        report = verify_release_zip(zip_path)
        external_dir = base / "external-clean"
        external_dir.mkdir()
        external_zip = external_dir / "release-export.zip"
        shutil.copy2(zip_path, external_zip)
        os.chdir(external_dir)
        external_report = verify_release_zip(external_zip)
        os.chdir(base)

        hash_mismatch_zip = _v38_rewrite_zip(zip_path, base / "hash-mismatch.zip", additions={"tracks/01-release-verifier-track-one/song.mid": b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff/\x00"})
        dangerous_zip = _v38_rewrite_zip(zip_path, base / "dangerous.zip", additions={"../evil.txt": b"x"})
        backslash_zip = _v38_backslash_entry_zip(base / "backslash.zip")
        duplicate_zip = base / "duplicate.zip"
        shutil.copy2(zip_path, duplicate_zip)
        with zipfile.ZipFile(duplicate_zip, "a") as archive:
            archive.writestr("README.txt", "duplicate")

        def spoof_manifest(data: bytes) -> bytes:
            manifest = json.loads(data.decode("utf-8"))
            manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
            return json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

        spoof_zip = _v38_rewrite_zip(zip_path, base / "spoofed-extra.zip", additions={"extra.txt": b"extra"}, transforms={"manifest.json": spoof_manifest})

        def pollute_release(data: bytes) -> bytes:
            release = json.loads(data.decode("utf-8"))
            release["notes"] = r"C:\Users\demo\secret.zip api_key=sk-secret-value"
            return json.dumps(release, ensure_ascii=False, indent=2).encode("utf-8")

        polluted_zip = _v38_rewrite_zip(zip_path, base / "polluted.zip", transforms={"release.json": pollute_release})

        def tamper_signoff(data: bytes) -> bytes:
            signoff = json.loads(data.decode("utf-8"))
            signoff["signed_by"] = "tampered-reviewer"
            signoff["signed_at"] = "2099-01-01T00:00:00+00:00"
            return json.dumps(signoff, ensure_ascii=False, indent=2).encode("utf-8")

        tampered_signoff_zip = _v38_rewrite_zip(zip_path, base / "tampered-signoff.zip", transforms={"release-signoff.json": tamper_signoff})
        bomb_zip = base / "bomb.zip"
        with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", b"0" * (1024 * 1024 + 1))

        hash_report = verify_release_zip(hash_mismatch_zip)
        dangerous_report = verify_release_zip(dangerous_zip)
        backslash_report = verify_release_zip(backslash_zip)
        duplicate_report = verify_release_zip(duplicate_zip)
        spoof_report = verify_release_zip(spoof_zip, strict=True)
        polluted_report = verify_release_zip(polluted_zip)
        tampered_signoff_report = verify_release_zip(tampered_signoff_zip)
        bomb_report = verify_release_zip(bomb_zip, max_uncompressed_size_mb=1)

        ok = (
            created_status == 201
            and release_id
            and add_first_status == 200
            and add_second_status == 200
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and export_status == 200
            and zip_status == 200
            and sign_status == 200
            and signed.get("summary", {}).get("status") == "signed"
            and report.get("status") == "warning"
            and external_report.get("status") == "warning"
            and _v38_check_status(hash_report, "manifest_file_hash_match") == "failed"
            and _v38_check_status(dangerous_report, "zip_entry_path_safe") == "failed"
            and _v38_check_status(backslash_report, "zip_entry_path_safe") == "failed"
            and _v38_check_status(duplicate_report, "zip_duplicate_entries") == "failed"
            and _v38_check_status(spoof_report, "manifest_extra_entries") == "failed"
            and _v38_check_status(polluted_report, "redaction_scan") == "failed"
            and _v38_check_status(tampered_signoff_report, "signoff_sidecar_payload_hash") == "failed"
            and _v38_check_status(bomb_report, "zip_uncompressed_size_limit") == "failed"
        )
        return ok, (
            f"release={release_id}, verify={report.get('status')}, external={external_report.get('status')}, "
            f"hash={_v38_check_status(hash_report, 'manifest_file_hash_match')}, dangerous={_v38_check_status(dangerous_report, 'zip_entry_path_safe')}, "
            f"backslash={_v38_check_status(backslash_report, 'zip_entry_path_safe')}, duplicate={_v38_check_status(duplicate_report, 'zip_duplicate_entries')}, "
            f"spoof={_v38_check_status(spoof_report, 'manifest_extra_entries')}, redaction={_v38_check_status(polluted_report, 'redaction_scan')}, "
            f"tampered_signoff={_v38_check_status(tampered_signoff_report, 'signoff_sidecar_payload_hash')}, bomb={_v38_check_status(bomb_report, 'zip_uncompressed_size_limit')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v38_rewrite_zip(source: Path, target: Path, *, additions: dict[str, bytes] | None = None, transforms: dict[str, Any] | None = None, remove: set[str] | None = None) -> Path:
    additions = additions or {}
    transforms = transforms or {}
    remove = remove or set()
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename in remove or info.filename in additions:
                continue
            data = src.read(info)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)
            dst.writestr(info.filename, data)
        for name, data in additions.items():
            dst.writestr(name, data)
    return target


def _v38_backslash_entry_zip(target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    data = target.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt")
    target.write_bytes(data)
    return target


def _v38_check_status(report: dict[str, Any], check_id: str) -> str | None:
    for check in [*report.get("checks", []), *report.get("track_checks", [])]:
        if isinstance(check, dict) and check.get("check_id") == check_id:
            return str(check.get("status"))
    return None


def _v38_check_message(report: dict[str, Any], check_id: str) -> str | None:
    for check in [*report.get("checks", []), *report.get("track_checks", [])]:
        if isinstance(check, dict) and check.get("check_id") == check_id:
            return str(check.get("message"))
    return None


def _v39_release_metadata_smoke(root: Path) -> tuple[bool, str]:
    base = (root / ".release-check" / "v39-release-metadata").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Release Metadata Track One")
        created_status, created = _release_http_json(
            server,
            "POST",
            "/api/releases",
            {"name": "Release Metadata Pack", "release_type": "demo_pack", "primary_artist": "MusicForge", "label": "Forge Label", "language": "English"},
        )
        release_id = created.get("release", {}).get("release_id")
        add_status, _added = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Release Metadata Track One"})
        init_status, initialized = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized.get("metadata", {})
        if isinstance(metadata.get("release"), dict):
            metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        if isinstance(metadata.get("tracks"), list) and metadata["tracks"]:
            metadata["tracks"][0].update({"isrc": "USABC2600001", "lyrics": "Release metadata lyric", "credits": [{"role": "composer", "name": "Release Writer", "source": "user"}], "confirmed": True})
        save_status, saved = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        metadata_qa_status, metadata_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        platform_status, platform_csv = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/metadata/platform.csv")
        credits_status, credits_csv = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/metadata/credits.csv")
        sign_status, signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})
        signed_export_status, signed_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        signed_zip_status, signed_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        signed_metadata_export_status, signed_metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        zip_path = base / ".musicforge" / "releases" / str(release_id) / "release-export.zip"
        verifier_report = verify_release_zip(zip_path)

        missing_zip = _v38_rewrite_zip(zip_path, base / "metadata-missing.zip", remove={"release-metadata.json"})

        def pollute_platform(data: bytes) -> bytes:
            return data + b'\n"1","1","C:\\Users\\demo\\secret.zip api_key=sk-secret-value"\n'

        polluted_zip = _v38_rewrite_zip(zip_path, base / "metadata-polluted.zip", transforms={"platform-metadata.csv": pollute_platform})
        missing_report = verify_release_zip(missing_zip)
        polluted_report = verify_release_zip(polluted_zip)
        serialized = json.dumps(
            {
                "saved": saved,
                "metadata_qa": metadata_qa,
                "exported": exported,
                "metadata_export": metadata_export,
                "signed": signed,
                "signed_export": signed_export,
                "signed_zip": signed_zip,
                "signed_metadata_export": signed_metadata_export,
            },
            ensure_ascii=False,
        )
        ok = (
            created_status == 201
            and release_id
            and add_status == 200
            and init_status == 200
            and initialized.get("metadata", {}).get("release", {}).get("title") == "Release Metadata Pack"
            and save_status == 200
            and saved.get("summary", {}).get("qa_status") == "passed"
            and metadata_qa_status == 200
            and metadata_qa.get("summary", {}).get("status") == "passed"
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and export_status == 200
            and exported.get("manifest", {}).get("metadata", {}).get("exists") is True
            and metadata_export_status == 200
            and metadata_export.get("summary", {}).get("status") == "exported"
            and platform_status == 200
            and b"USABC2600001" in platform_csv
            and credits_status == 200
            and b"Release Writer" in credits_csv
            and sign_status == 200
            and signed.get("summary", {}).get("status") == "signed"
            and signed_export_status == 409
            and signed_zip_status == 409
            and signed_metadata_export_status == 409
            and "signed" in signed_export.get("error", "").lower()
            and "signed" in signed_zip.get("error", "").lower()
            and "signed" in signed_metadata_export.get("error", "").lower()
            and verifier_report.get("status") == "passed"
            and _v38_check_status(verifier_report, "metadata_payload_hash") == "passed"
            and _v38_check_status(missing_report, "metadata_files_present") == "failed"
            and _v38_check_status(polluted_report, "manifest_file_hash_match") == "failed"
            and _v38_check_status(polluted_report, "redaction_scan") == "failed"
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, (
            f"release={release_id}, metadata_qa={metadata_qa.get('summary', {}).get('status')}, verify={verifier_report.get('status')}, "
            f"signed_export={signed_export_status}/{signed_zip_status}/{signed_metadata_export_status}, "
            f"missing={_v38_check_status(missing_report, 'metadata_files_present')}, polluted={_v38_check_status(polluted_report, 'redaction_scan')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v40_distribution_prep_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v40-distribution-prep").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Distribution Prep Track")
        created_status, created = _release_http_json(
            server,
            "POST",
            "/api/releases",
            {"name": "Distribution Prep Pack", "release_type": "demo_pack", "primary_artist": "MusicForge", "label": "Forge Label", "language": "English"},
        )
        release_id = created.get("release", {}).get("release_id")
        add_status, _added = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Distribution Prep Track"})
        init_status, initialized = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized.get("metadata", {})
        if isinstance(metadata.get("release"), dict):
            metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        if isinstance(metadata.get("tracks"), list) and metadata["tracks"]:
            metadata["tracks"][0].update({"title": "=Distribution Prep Track", "isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Distribution Writer"}], "confirmed": True})
        save_status, _saved = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        metadata_qa_status, metadata_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, _metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        sign_status, _signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})
        profiles_status, profiles = _release_http_json(server, "GET", "/api/distribution/profiles")
        target_status, target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Distribution Prep Target"})
        target_id = target.get("target", {}).get("target_id")
        local_cover = base / "server-cover.png"
        local_cover.write_bytes(_v40_png(1400, 1400))
        source_path_status, source_path_error = _release_http_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/artwork/import",
            {"filename": "cover.png", "source_path": str(local_cover)},
        )
        artwork_before_status, artwork_before = _release_http_json(server, "GET", f"/api/releases/{release_id}/distribution/artwork")
        artwork_status, artwork = _release_http_json(
            server,
            "POST",
            f"/api/releases/{release_id}/distribution/artwork/import",
            {"filename": "cover.png", "content_base64": base64.b64encode(_v40_png(1400, 1400)).decode("ascii")},
        )
        artwork_id = artwork.get("artwork", {}).get("artwork_id")
        update_status, _updated = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork_id, "submission_note": "=spreadsheet guard"}})
        dist_qa_status, dist_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        dist_export_status, dist_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        dist_zip_status, dist_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, dist_signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "release-check"})
        qa_path = base / ".musicforge" / "releases" / str(release_id) / "distribution" / "qa" / f"{target_id}-qa.json"
        qa_before_repeat_signoff = qa_path.read_bytes() if qa_path.exists() else b""
        repeat_sign_status, repeat_signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "release-check"})
        qa_after_repeat_signoff = qa_path.read_bytes() if qa_path.exists() else b""
        dist_verify_status, dist_verify = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/verify", {"require_artwork": True})
        zip_download_status, zip_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/export.zip")
        blocked_export_status, blocked_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        blocked_qa_status, blocked_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")

        package_id = dist_export.get("manifest", {}).get("package_id")
        if zip_download_status != 200 or not zip_bytes.startswith(b"PK"):
            return False, (
                f"distribution zip download failed: status={zip_download_status}, prefix={zip_bytes[:80]!r}, "
                f"release={release_id}, target={target_id}, package={package_id}, "
                f"dist_export={dist_export_status}:{dist_export}, dist_zip={dist_zip_status}:{dist_zip}, "
                f"dist_sign={dist_sign_status}:{dist_signed}"
            )
        zip_path = base / "distribution-package.zip"
        zip_path.write_bytes(zip_bytes)
        external_dir = base / "external-clean"
        external_dir.mkdir()
        external_zip = external_dir / "distribution-package.zip"
        shutil.copy2(zip_path, external_zip)
        old_external_cwd = Path.cwd()
        os.chdir(external_dir)
        external_report = verify_distribution_package(external_zip, require_artwork=True)
        os.chdir(old_external_cwd)

        def tamper_signoff(data: bytes) -> bytes:
            signoff = json.loads(data.decode("utf-8"))
            signoff["signed_by"] = "tampered-reviewer"
            return json.dumps(signoff, ensure_ascii=False, indent=2).encode("utf-8")

        def unescape_platform(data: bytes) -> bytes:
            return data.replace(b"'=", b"=")

        tampered_zip = _v38_rewrite_zip(zip_path, base / "tampered-distribution-signoff.zip", transforms={"distribution-signoff.json": tamper_signoff})
        formula_zip = _v38_rewrite_zip(zip_path, base / "formula-distribution.csv.zip", transforms={"platform-metadata.csv": unescape_platform})
        backslash_zip = _v38_backslash_entry_zip(base / "distribution-backslash.zip")
        tampered_report = verify_distribution_package(tampered_zip)
        formula_report = verify_distribution_package(formula_zip)
        backslash_report = verify_distribution_package(backslash_zip)

        reset_status, reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff/reset", {"reason": r"rebuild distribution C:\Users\demo"})
        export_after_reset_status, _after_reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        serialized = json.dumps({"dist_signed": dist_signed, "blocked_export": blocked_export, "blocked_qa": blocked_qa, "reset": reset}, ensure_ascii=False)
        ok = (
            created_status == 201
            and release_id
            and add_status == 200
            and init_status == 200
            and save_status == 200
            and metadata_qa_status == 200
            and metadata_qa.get("summary", {}).get("status") == "passed"
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and export_status == 200
            and metadata_export_status == 200
            and sign_status == 200
            and profiles_status == 200
            and any(item.get("profile_id") == "demo_pitch" for item in profiles.get("profiles", []))
            and target_status == 201
            and source_path_status == 400
            and "source_path" in str(source_path_error.get("error") or "")
            and artwork_before_status == 200
            and artwork_before.get("artwork") == []
            and artwork_status == 201
            and update_status == 200
            and dist_qa_status == 200
            and dist_qa.get("summary", {}).get("status") in {"passed", "warning"}
            and dist_export_status == 201
            and dist_zip_status == 200
            and dist_zip.get("zip", {}).get("sha256")
            and dist_sign_status == 200
            and dist_signed.get("summary", {}).get("status") == "signed"
            and repeat_sign_status == 409
            and "signed" in str(repeat_signoff.get("error") or "").lower()
            and qa_after_repeat_signoff == qa_before_repeat_signoff
            and dist_verify_status == 200
            and dist_verify.get("summary", {}).get("status") == "passed"
            and zip_download_status == 200
            and zip_bytes.startswith(b"PK")
            and external_report.get("status") == "passed"
            and blocked_export_status == 409
            and blocked_qa_status == 409
            and _v38_check_status(tampered_report, "distribution_signoff_sidecar_payload_hash") == "failed"
            and _v38_check_status(formula_report, "distribution_csv_formula_safe") == "failed"
            and _v38_check_status(backslash_report, "zip_entry_path_safe") == "failed"
            and reset_status == 200
            and reset.get("summary", {}).get("status") == "reset"
            and export_after_reset_status == 201
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, (
            f"release={release_id}, target={target_id}, qa={dist_qa.get('summary', {}).get('status')}, "
            f"verify={dist_verify.get('summary', {}).get('status')}, external={external_report.get('status')}, "
            f"source_path={source_path_status}, repeat_sign={repeat_sign_status}, blocked={blocked_export_status}/{blocked_qa_status}, "
            f"tampered={_v38_check_status(tampered_report, 'distribution_signoff_sidecar_payload_hash')}, "
            f"formula={_v38_check_status(formula_report, 'distribution_csv_formula_safe')}, backslash={_v38_check_status(backslash_report, 'zip_entry_path_safe')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v40_png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + b"\x00" * 16


def _v41_distribution_template_packs_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v41-distribution-template-packs").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Template Pack Track")
        created_status, created = _release_http_json(server, "POST", "/api/releases", {"name": "Template Pack Release", "release_type": "demo_pack", "primary_artist": "MusicForge", "label": "Forge Label", "language": "English"})
        release_id = created.get("release", {}).get("release_id")
        add_status, _added = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Template Pack Track"})
        init_status, initialized = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized.get("metadata", {})
        if isinstance(metadata.get("release"), dict):
            metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        if isinstance(metadata.get("tracks"), list) and metadata["tracks"]:
            metadata["tracks"][0].update({"title": "Template Pack Track", "isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Template Writer"}], "confirmed": True})
        save_status, _saved = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        metadata_qa_status, metadata_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, _metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        sign_status, _signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})

        template_payload = {
            "slug": "release-check-template-basic",
            "name": "Release Check Template Basic",
            "rules": {"require_artwork": True, "require_upc": True, "require_isrc": True, "csv_formula_escape": True},
            "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}, {"column": "ISRC", "source": "track.isrc", "required": True}]},
            "file_naming": {"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.{ext}"},
            "checklist": [{"item_id": "explicit-confirmed", "label": "Explicit flag checked", "required": True}],
        }
        templates_status, templates = _release_http_json(server, "GET", "/api/distribution/template-packs")
        template_status, template = _release_http_json(server, "POST", "/api/distribution/template-packs", template_payload)
        template_id = template.get("template", {}).get("template_pack_id")
        source_path_status, source_path_error = _release_http_json(server, "POST", "/api/distribution/template-packs/import", {"source_path": str(base / "template.json"), "template": template.get("template", {})})
        validate_bad_status, validate_bad = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}/validate", {"template": {**template_payload, "description": "api_key=sk-secret-value"}})
        export_template_status, exported_template = _release_http_json(server, "GET", f"/api/distribution/template-packs/{template_id}/export")
        import_status, imported_template = _release_http_json(server, "POST", "/api/distribution/template-packs/import?rename=true", {"template": exported_template.get("template", {})})

        target_status, target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "template_pack_id": template_id, "name": "Template Target"})
        target_id = target.get("target", {}).get("target_id")
        blocked_unsigned_template_delete_status, blocked_unsigned_template_delete = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}/delete")
        artwork_status, artwork = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_v40_png(1400, 1400)).decode("ascii")})
        artwork_id = artwork.get("artwork", {}).get("artwork_id")
        update_status, _updated = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork_id}})
        checklist_status, checklist = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist")
        qa_failed_status, qa_failed = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        checklist_done_status, checklist_done = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist/items/explicit-confirmed", {"status": "done", "note": "Checked by release-check"})
        dist_qa_status, dist_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        dist_export_status, dist_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        dist_zip_status, dist_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, dist_signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "release-check"})
        dist_verify_status, dist_verify = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/verify", {"require_artwork": True})
        blocked_checklist_status, blocked_checklist = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist/items/explicit-confirmed", {"status": "blocked"})
        blocked_template_status, blocked_template = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"template_pack_id": imported_template.get("template", {}).get("template_pack_id")})
        blocked_template_update_status, blocked_template_update = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}", {"name": "Changed After Signoff"})
        blocked_template_delete_status, blocked_template_delete = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}/delete")
        zip_status, zip_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/export.zip")
        zip_path = base / "template-distribution.zip"
        zip_path.write_bytes(zip_bytes)

        def tamper_template(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["name"] = "Tampered"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        def tamper_checklist(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["items"][0]["status"] = "blocked"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        tampered_template_report = verify_distribution_package(_v38_rewrite_zip(zip_path, base / "template-tampered.zip", transforms={"template-pack.json": tamper_template}), require_artwork=True)
        tampered_checklist_report = verify_distribution_package(_v38_rewrite_zip(zip_path, base / "checklist-tampered.zip", transforms={"docs/checklist.json": tamper_checklist}), require_artwork=True)
        external_dir = base / "external-clean"
        external_dir.mkdir()
        external_zip = external_dir / "template-distribution.zip"
        shutil.copy2(zip_path, external_zip)
        old_external_cwd = Path.cwd()
        os.chdir(external_dir)
        external_report = verify_distribution_package(external_zip, require_artwork=True)
        os.chdir(old_external_cwd)

        serialized = json.dumps(
            {
                "template": template,
                "dist_export": dist_export,
                "blocked_checklist": blocked_checklist,
                "blocked_template": blocked_template,
                "blocked_unsigned_template_delete": blocked_unsigned_template_delete,
                "blocked_template_update": blocked_template_update,
                "blocked_template_delete": blocked_template_delete,
            },
            ensure_ascii=False,
        )
        ok = (
            created_status == 201
            and release_id
            and add_status == 200
            and init_status == 200
            and save_status == 200
            and metadata_qa_status == 200
            and metadata_qa.get("summary", {}).get("status") == "passed"
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and export_status == 200
            and metadata_export_status == 200
            and sign_status == 200
            and templates_status == 200
            and any(item.get("slug") == "generic-dsp-basic" for item in templates.get("template_packs", []))
            and template_status == 201
            and source_path_status == 400
            and "source_path" in str(source_path_error.get("error") or "")
            and validate_bad_status == 200
            and validate_bad.get("validation", {}).get("status") == "failed"
            and export_template_status == 200
            and import_status == 201
            and imported_template.get("template", {}).get("content_hash") == template.get("template", {}).get("content_hash")
            and target_status == 201
            and target.get("target", {}).get("template_pack_id") == template_id
            and blocked_unsigned_template_delete_status == 409
            and "unbind" in str(blocked_unsigned_template_delete.get("error") or "").lower()
            and artwork_status == 201
            and update_status == 200
            and checklist_status == 200
            and checklist.get("summary", {}).get("status") == "failed"
            and qa_failed_status == 200
            and qa_failed.get("summary", {}).get("status") == "failed"
            and checklist_done_status == 200
            and checklist_done.get("summary", {}).get("status") == "passed"
            and dist_qa_status == 200
            and dist_qa.get("summary", {}).get("status") in {"passed", "warning"}
            and dist_export_status == 201
            and dist_export.get("manifest", {}).get("template", {}).get("template_hash") == template.get("template", {}).get("template_hash")
            and dist_export.get("manifest", {}).get("checklist", {}).get("status") == "passed"
            and dist_zip_status == 200
            and dist_zip.get("zip", {}).get("sha256")
            and dist_sign_status == 200
            and dist_signed.get("summary", {}).get("status") == "signed"
            and dist_verify_status == 200
            and dist_verify.get("summary", {}).get("status") == "passed"
            and blocked_checklist_status == 409
            and blocked_template_status == 409
            and blocked_template_update_status == 409
            and "signed" in str(blocked_template_update.get("error") or "").lower()
            and blocked_template_delete_status == 409
            and "signed" in str(blocked_template_delete.get("error") or "").lower()
            and zip_status == 200
            and zip_bytes.startswith(b"PK")
            and external_report.get("status") == "passed"
            and _v38_check_status(tampered_template_report, "distribution_template_hash_match") == "failed"
            and _v38_check_status(tampered_checklist_report, "distribution_checklist_payload_hash") == "failed"
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, (
            f"release={release_id}, target={target_id}, template={template_id}, "
            f"pending_qa={qa_failed.get('summary', {}).get('status')}, qa={dist_qa.get('summary', {}).get('status')}, "
            f"verify={dist_verify.get('summary', {}).get('status')}, external={external_report.get('status')}, "
            f"source_path={source_path_status}, blocked={blocked_unsigned_template_delete_status}/{blocked_checklist_status}/{blocked_template_status}/{blocked_template_update_status}/{blocked_template_delete_status}, "
            f"template_tamper={_v38_check_status(tampered_template_report, 'distribution_template_hash_match')}, "
            f"checklist_tamper={_v38_check_status(tampered_checklist_report, 'distribution_checklist_payload_hash')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v42_distribution_layout_contract_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v42-distribution-layout-contract").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Layout Contract Track")
        created_status, created = _release_http_json(server, "POST", "/api/releases", {"name": "Layout Contract Release", "release_type": "demo_pack", "primary_artist": "MusicForge", "label": "Forge Label", "language": "English"})
        release_id = created.get("release", {}).get("release_id")
        add_status, _added = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Layout Contract Track"})
        init_status, initialized = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized.get("metadata", {})
        if isinstance(metadata.get("release"), dict):
            metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        if isinstance(metadata.get("tracks"), list) and metadata["tracks"]:
            metadata["tracks"][0].update({"title": "Layout Contract Track", "isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Layout Writer"}], "confirmed": True})
        save_status, _saved = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        metadata_qa_status, metadata_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        qa_status, qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, _metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        sign_status, _signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})

        template_payload = {
            "slug": "layout-contract-template",
            "name": "Layout Contract Template",
            "rules": {"require_artwork": True, "require_upc": True, "require_isrc": True, "csv_formula_escape": True},
            "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}]},
            "file_naming": {
                "audio": "tracks/disc-{disc_number}/{track_number:02d}-{slug_title}.{ext}",
                "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt",
                "artwork": "artwork/{release_slug}-cover.{ext}",
            },
            "checklist": [{"item_id": "explicit-confirmed", "label": "Explicit flag checked", "required": True}],
        }
        template_status, template = _release_http_json(server, "POST", "/api/distribution/template-packs", template_payload)
        template_id = template.get("template", {}).get("template_pack_id")
        bad_artwork_status, bad_artwork = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}/validate", {"template": {**template_payload, "file_naming": {"artwork": "artwork/{slug_title}.{ext}"}}})
        unsafe_status, unsafe = _release_http_json(server, "POST", f"/api/distribution/template-packs/{template_id}/validate", {"template": {**template_payload, "file_naming": {"audio": "../x.wav"}}})
        collision_status, collision_template = _release_http_json(server, "POST", "/api/distribution/template-packs", {**template_payload, "slug": "layout-collision-template", "name": "Layout Collision Template", "file_naming": {"audio": "audio/song.{ext}", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt", "artwork": "artwork/{release_slug}-cover.{ext}"}})
        hardcoded_wav_status, hardcoded_wav_template = _release_http_json(server, "POST", "/api/distribution/template-packs", {**template_payload, "slug": "layout-hardcoded-wav-template", "name": "Layout Hardcoded WAV Template", "file_naming": {"audio": "audio/{track_number:02d}-{slug_title}.wav", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt", "artwork": "artwork/{release_slug}-cover.{ext}"}})

        target_status, target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "template_pack_id": template_id, "name": "Layout Target"})
        target_id = target.get("target", {}).get("target_id")
        artwork_status, artwork = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_v40_png(1400, 1400)).decode("ascii")})
        artwork_id = artwork.get("artwork", {}).get("artwork_id")
        update_status, _updated = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork_id}})
        checklist_status, _checklist = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist")
        checklist_done_status, _done = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist/items/explicit-confirmed", {"status": "done", "note": "Checked by release-check"})
        layout_status, layout = _release_http_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/layout")
        dist_qa_status, dist_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        dist_export_status, dist_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        dist_zip_status, _dist_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, dist_signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "release-check"})
        zip_status, zip_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/export.zip")
        zip_path = base / "layout-distribution.zip"
        zip_path.write_bytes(zip_bytes)
        report = verify_distribution_package(zip_path, require_artwork=True)
        external_dir = base / "external-clean"
        external_dir.mkdir()
        external_zip = external_dir / "layout-distribution.zip"
        shutil.copy2(zip_path, external_zip)
        old_external_cwd = Path.cwd()
        os.chdir(external_dir)
        external_report = verify_distribution_package(external_zip, require_artwork=True)
        os.chdir(old_external_cwd)

        def tamper_layout(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["entries"][0]["path"] = "audio/tampered.wav"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        def tamper_artwork_path(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["artwork"]["package_path"] = "artwork/missing.png"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        layout_tamper = verify_distribution_package(_v38_rewrite_zip(zip_path, base / "layout-tampered.zip", transforms={"layout/manifest-layout.json": tamper_layout}), require_artwork=True)
        artwork_tamper = verify_distribution_package(_v38_rewrite_zip(zip_path, base / "artwork-path-tampered.zip", transforms={"distribution-manifest.json": tamper_artwork_path}), require_artwork=True)

        def poison_template(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["file_naming"]["audio"] = "../x.wav"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        bad_template_pack_report = verify_distribution_package(_v38_rewrite_zip(zip_path, base / "bad-template-pack.zip", transforms={"template-pack.json": poison_template}), require_artwork=True)

        hardcoded_target_status, hardcoded_target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "template_pack_id": hardcoded_wav_template.get("template", {}).get("template_pack_id"), "name": "Hardcoded WAV Layout Target"})
        hardcoded_target_id = hardcoded_target.get("target", {}).get("target_id")
        hardcoded_update_status, _hardcoded_update = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{hardcoded_target_id}", {"options": {"artwork_id": artwork_id}})
        hardcoded_layout_status, hardcoded_layout = _release_http_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{hardcoded_target_id}/layout")
        hardcoded_qa_status, hardcoded_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{hardcoded_target_id}/qa/refresh")
        hardcoded_export_status, _hardcoded_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{hardcoded_target_id}/export")
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        expected_audio = "tracks/disc-1/01-layout-contract-track.mid"
        expected_artwork = "artwork/layout-contract-release-cover.png"
        expected_lyrics = "lyrics/01-layout-contract-track.txt"
        serialized = json.dumps({"layout": layout, "dist_export": dist_export}, ensure_ascii=False)
        ok = (
            created_status == 201
            and add_status == 200
            and init_status == 200
            and save_status == 200
            and metadata_qa_status == 200
            and metadata_qa.get("summary", {}).get("status") == "passed"
            and qa_status == 200
            and qa.get("summary", {}).get("status") in {"passed", "warning"}
            and export_status == 200
            and metadata_export_status == 200
            and sign_status == 200
            and template_status == 201
            and bad_artwork_status == 200
            and bad_artwork.get("validation", {}).get("status") == "failed"
            and unsafe_status == 200
            and unsafe.get("validation", {}).get("status") == "failed"
            and collision_status == 201
            and collision_template.get("template", {}).get("template_pack_id")
            and hardcoded_wav_status == 201
            and target_status == 201
            and artwork_status == 201
            and update_status == 200
            and checklist_status == 200
            and checklist_done_status == 200
            and layout_status == 200
            and layout.get("summary", {}).get("status") == "passed"
            and expected_audio in [entry.get("path") for entry in layout.get("layout", {}).get("entries", [])]
            and dist_qa_status == 200
            and dist_qa.get("summary", {}).get("status") in {"passed", "warning"}
            and dist_export_status == 201
            and dist_export.get("layout_summary", {}).get("status") == "passed"
            and dist_export.get("manifest", {}).get("artwork", {}).get("package_path") == expected_artwork
            and dist_zip_status == 200
            and dist_sign_status == 200
            and dist_signed.get("summary", {}).get("status") == "signed"
            and zip_status == 200
            and zip_bytes.startswith(b"PK")
            and expected_audio in names
            and expected_artwork in names
            and expected_lyrics in names
            and "layout/manifest-layout.json" in names
            and "layout/file-tree.txt" in names
            and report.get("status") == "passed"
            and external_report.get("status") == "passed"
            and _v38_check_status(layout_tamper, "distribution_layout_hash_match") == "failed"
            and _v38_check_status(artwork_tamper, "distribution_artwork_package_path_match") == "failed"
            and _v38_check_status(bad_template_pack_report, "distribution_layout_template_pattern_parse") == "failed"
            and hardcoded_target_status == 201
            and hardcoded_update_status == 200
            and hardcoded_layout_status == 200
            and hardcoded_layout.get("summary", {}).get("status") == "failed"
            and hardcoded_qa_status == 200
            and hardcoded_qa.get("summary", {}).get("status") == "failed"
            and hardcoded_export_status == 409
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, (
            f"target={target_id}, layout={layout.get('summary', {}).get('status')}, "
            f"audio={expected_audio}, artwork={expected_artwork}, lyrics={expected_lyrics}, "
            f"sign={dist_sign_status}:{dist_signed.get('summary', {}).get('status')}, external={external_report.get('status')}, layout_tamper={_v38_check_status(layout_tamper, 'distribution_layout_hash_match')}, "
            f"artwork_path_tamper={_v38_check_status(artwork_tamper, 'distribution_artwork_package_path_match')}, "
            f"bad_template_pack={_v38_check_status(bad_template_pack_report, 'distribution_layout_template_pattern_parse')}, "
            f"hardcoded_wav={hardcoded_layout.get('summary', {}).get('status')}/{hardcoded_qa.get('summary', {}).get('status')}/{hardcoded_export_status}, "
            f"unsafe_pattern={unsafe.get('validation', {}).get('status')}, bad_artwork_var={bad_artwork.get('validation', {}).get('status')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v43_submission_workspace_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v43-submission-workspace").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Submission Workspace Track")
        created_status, created = _release_http_json(server, "POST", "/api/releases", {"name": "Submission Workspace Release", "release_type": "demo_pack", "primary_artist": "MusicForge", "label": "Forge Label", "language": "English"})
        release_id = created.get("release", {}).get("release_id")
        add_status, _added = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Submission Workspace Track"})
        init_status, initialized = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized.get("metadata", {})
        if isinstance(metadata.get("release"), dict):
            metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        if isinstance(metadata.get("tracks"), list) and metadata["tracks"]:
            metadata["tracks"][0].update({"title": "Submission Workspace Track", "isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Submission Writer"}], "confirmed": True})
        save_status, _saved = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        metadata_qa_status, _metadata_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, _metadata_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        sign_status, _signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})

        target_status, target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Submission DSP Target"})
        target_id = target.get("target", {}).get("target_id")
        artwork_status, artwork = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_v40_png(1400, 1400)).decode("ascii")})
        artwork_id = artwork.get("artwork", {}).get("artwork_id")
        update_status, _updated = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork_id}})
        dist_qa_status, dist_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        dist_export_status, _dist_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        dist_zip_status, _dist_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, _dist_signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "release-check"})

        sub_create_status, sub_created = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Release Check Submission", "target_ids": [target_id]})
        submission_id = sub_created.get("submission", {}).get("submission_id")
        item_id = (sub_created.get("submission", {}).get("items") or [{}])[0].get("item_id")
        sub_qa_status, sub_qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        sub_export_status, sub_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        sub_zip_status, _sub_zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        pre_sign_submit_status, pre_sign_submit = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-submission", {"external_reference": "PRE-SIGN"})
        sub_sign_status, sub_signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "release-check", "notes": r"accepted C:\Users\demo api_key=sk-secret-value"})
        blocked_add_status, blocked_add = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/targets", {"target_id": target_id})
        blocked_export_status, blocked_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        submitted_status, submitted = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-submission", {"external_reference": "DSP-SUB-1"})
        feedback_status, feedback = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-feedback", {"status": "needs_changes", "message": "metadata note"})
        accepted_status, accepted = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/accepted", {"external_reference": "DSP-SUB-1"})
        verify_status, verified = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/verify", {"deep": True})
        zip_status, zip_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}/export.zip")
        zip_path = base / "submission-package.zip"
        zip_path.write_bytes(zip_bytes)
        external_dir = base / "external-clean"
        external_dir.mkdir()
        external_zip = external_dir / "submission-package.zip"
        shutil.copy2(zip_path, external_zip)
        old_external_cwd = Path.cwd()
        os.chdir(external_dir)
        external_report = verify_submission_package(external_zip, deep=True)
        os.chdir(old_external_cwd)

        def tamper_signoff(data: bytes) -> bytes:
            value = json.loads(data.decode("utf-8"))
            value["signed_by"] = "tampered-reviewer"
            return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

        def tamper_target_zip(data: bytes) -> bytes:
            return data + b"tampered"

        tampered_signoff = verify_submission_package(_v38_rewrite_zip(zip_path, base / "submission-signoff-tampered.zip", transforms={"submission-signoff.json": tamper_signoff}))
        tampered_target = verify_submission_package(_v38_rewrite_zip(zip_path, base / "submission-target-tampered.zip", transforms={f"targets/{target_id}/distribution-package.zip": tamper_target_zip}))
        backslash_report = verify_submission_package(_v43_backslash_submission_zip(base / "submission-backslash.zip"))
        duplicate_report = verify_submission_package(_v43_duplicate_submission_zip(zip_path, base / "submission-duplicate.zip"))

        pending_target_status, pending_target = _release_http_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Submission Pending Target"})
        pending_target_id = pending_target.get("target", {}).get("target_id")
        pending_create_status, pending_created = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Pending Submission", "target_ids": [pending_target_id]})
        pending_submission_id = pending_created.get("submission", {}).get("submission_id")
        pending_item_id = (pending_created.get("submission", {}).get("items") or [{}])[0].get("item_id")
        pending_unsigned_submit_status, pending_unsigned_submit = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{pending_submission_id}/items/{pending_item_id}/record-submission", {"external_reference": "UNSIGNED-SUB"})
        server.submission_store.update_signoff_summary(release_id, pending_submission_id, {"status": "signed", "source": "release-check-regression"})
        pending_signed_submit_status, pending_signed_submit = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{pending_submission_id}/items/{pending_item_id}/record-submission", {"external_reference": "PENDING-SUB"})
        pending_signed_accept_status, pending_signed_accept = _release_http_json(server, "POST", f"/api/releases/{release_id}/submissions/{pending_submission_id}/items/{pending_item_id}/accepted", {"external_reference": "PENDING-SUB"})
        serialized = json.dumps({"sub_signed": sub_signed, "sub_export": sub_export, "verified": verified}, ensure_ascii=False)
        ok = (
            created_status == 201
            and add_status == 200
            and init_status == 200
            and save_status == 200
            and metadata_qa_status == 200
            and qa_status == 200
            and export_status == 200
            and metadata_export_status == 200
            and sign_status == 200
            and target_status == 201
            and artwork_status == 201
            and update_status == 200
            and dist_qa_status == 200
            and dist_qa.get("summary", {}).get("status") in {"passed", "warning"}
            and dist_export_status == 201
            and dist_zip_status == 200
            and dist_sign_status == 200
            and sub_create_status == 201
            and sub_qa_status == 200
            and sub_qa.get("summary", {}).get("status") in {"passed", "warning"}
            and sub_export_status == 201
            and sub_zip_status == 200
            and pre_sign_submit_status == 409
            and sub_sign_status == 200
            and sub_signed.get("summary", {}).get("status") == "signed"
            and blocked_add_status == 409
            and blocked_export_status == 409
            and "signed" in blocked_add.get("error", "").lower()
            and "signed" in blocked_export.get("error", "").lower()
            and submitted_status == 200
            and submitted.get("summary", {}).get("status") == "submitted"
            and feedback_status == 200
            and feedback.get("summary", {}).get("status") == "needs_changes"
            and accepted_status == 200
            and accepted.get("summary", {}).get("status") == "accepted"
            and verify_status == 200
            and verified.get("summary", {}).get("status") == "passed"
            and zip_status == 200
            and zip_bytes.startswith(b"PK")
            and external_report.get("status") == "passed"
            and _v38_check_status(tampered_signoff, "submission_signoff_sidecar_payload_hash") == "failed"
            and _v43_any_check_status(tampered_target, "target_distribution_zip_hash_match") == "failed"
            and _v38_check_status(backslash_report, "zip_entry_path_safe") == "failed"
            and _v38_check_status(duplicate_report, "zip_duplicate_entries") == "failed"
            and pending_target_status == 201
            and pending_create_status == 201
            and pending_unsigned_submit_status == 409
            and pending_signed_submit_status == 409
            and pending_signed_accept_status == 409
            and "signed" in pre_sign_submit.get("error", "").lower()
            and "signed" in pending_unsigned_submit.get("error", "").lower()
            and ("ready" in pending_signed_submit.get("error", "").lower() or "one of" in pending_signed_submit.get("error", "").lower())
            and "one of" in pending_signed_accept.get("error", "").lower()
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
            and str(base) not in serialized
        )
        return ok, (
            f"submission={submission_id}, sign={sub_signed.get('summary', {}).get('status')}, "
            f"verify={verified.get('summary', {}).get('status')}, external={external_report.get('status')}, "
            f"signoff_tamper={_v38_check_status(tampered_signoff, 'submission_signoff_sidecar_payload_hash')}, "
            f"target_tamper={_v43_any_check_status(tampered_target, 'target_distribution_zip_hash_match')}, "
            f"backslash={_v38_check_status(backslash_report, 'zip_entry_path_safe')}, duplicate={_v38_check_status(duplicate_report, 'zip_duplicate_entries')}, "
            f"pre_sign={pre_sign_submit_status}, pending={pending_signed_submit_status}/{pending_signed_accept_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v43_backslash_submission_zip(target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("submission-manifest.json", "{}")
        archive.writestr("submission-signoff.json", "{}")
        archive.writestr("submission-report.json", "{}")
        archive.writestr("submission-targets.csv", "a\n")
        archive.writestr("submission-events.jsonl", "")
        archive.writestr("README.txt", "readme")
        archive.writestr("extra/name.txt", "x")
    target.write_bytes(target.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))
    return target


def _v43_duplicate_submission_zip(source: Path, target: Path) -> Path:
    shutil.copy2(source, target)
    with zipfile.ZipFile(target, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "duplicate")
    return target


def _v43_any_check_status(report: dict[str, Any], check_id: str) -> str | None:
    for check in [*(report.get("checks", []) if isinstance(report.get("checks"), list) else []), *(report.get("item_checks", []) if isinstance(report.get("item_checks"), list) else [])]:
        if isinstance(check, dict) and check.get("check_id") == check_id:
            return str(check.get("status") or "")
    return None


def _v44_music_acceptance_lab_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v44-music-acceptance-lab").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        create_status, created = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.4 smoke acceptance", "min_rating": 3})
        suite_id = created.get("suite", {}).get("suite_id")
        case_ids: list[str] = []
        for index, style in enumerate(("upbeat pop", "instrumental cinematic"), start=1):
            case_status, case = _release_http_json(
                server,
                "POST",
                f"/api/acceptance/suites/{suite_id}/cases",
                {"name": style, "request": {"title": f"Acceptance Smoke {index}", "language": "English", "style": style, "theme": "release check", "duration_seconds": 90}},
            )
            case_id = case.get("case", {}).get("case_id")
            case_ids.append(case_id)
            generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
            health_status, health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
            review_status, review = _release_http_json(
                server,
                "POST",
                f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
                {"rating": 4, "status": "accepted", "playback_confirmed": True, "listened_by": "release-check", "audio_mode": "midi", "review_mode": "synthetic", "notes": r"Synthetic review confirms MIDI playback and structure; api_key=sk-secret-value C:\Users\demo\song.wav"},
            )
            if not (
                case_status == 201
                and generate_status == 200
                and health_status == 200
                and health.get("health", {}).get("status") in {"passed", "warning"}
                and health.get("health", {}).get("summary", {}).get("audio_status") == "skipped_renderer_not_configured"
                and review_status == 200
                and review.get("summary", {}).get("review_mode") == "synthetic"
            ):
                return False, f"case={case_id}, generate={generate_status}, health={health_status}, review={review_status}"
        report_status, report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        sign_status, signed = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/signoff", {"signed_by": "release-check"})
        blocked_status, blocked = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_ids[0]}/review",
            {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Should be blocked after signoff.", "audio_mode": "midi"},
        )
        report_path = base / ".musicforge" / "acceptance" / str(suite_id) / "music-acceptance-report.json"
        tampered_report = read_json(report_path)
        tampered_report["status"] = "passed" if tampered_report.get("status") != "passed" else "failed"
        write_json(report_path, tampered_report)
        tampered_status, tampered = _release_http_json(server, "GET", f"/api/acceptance/suites/{suite_id}/report")
        signoff_check_status, signoff_check = _release_http_json(server, "GET", f"/api/acceptance/suites/{suite_id}/signoff")

        store = AcceptanceStore(base / ".musicforge" / "acceptance")
        missing_suite = store.create_suite({"name": "missing midi regression"})
        missing_case = store.add_case(missing_suite.suite_id, {"request": {"title": "Missing MIDI", "language": "English", "style": "pop", "theme": "bad", "duration_seconds": 90}})
        store.generate_case(missing_suite.suite_id, missing_case.case_id, render_audio_mode="never")
        (store.case_dir(missing_suite.suite_id, missing_case.case_id) / "song.mid").unlink()
        missing_health = store.run_health(missing_suite.suite_id, missing_case.case_id)

        serialized = json.dumps({"report": report, "signed": signed}, ensure_ascii=False)
        ok = (
            create_status == 201
            and len(case_ids) == 2
            and report_status == 200
            and report.get("summary", {}).get("status") == "passed"
            and sign_status == 200
            and signed.get("summary", {}).get("status") == "signed"
            and blocked_status == 409
            and "signed" in blocked.get("error", "").lower()
            and tampered_status == 200
            and tampered.get("summary", {}).get("status") == "failed"
            and tampered.get("report", {}).get("verification", {}).get("content_status") == "failed"
            and signoff_check_status == 200
            and signoff_check.get("signoff", {}).get("report_integrity", {}).get("status") == "failed"
            and missing_health.get("status") == "failed"
            and any(item.get("check_id") == "midi_exists" for item in missing_health.get("blockers", []))
            and "sk-secret-value" not in serialized
            and "api_key" not in serialized
            and "C:\\Users" not in serialized
        )
        first_health = (report.get("report", {}).get("cases") or [{}])[0].get("health_status") if isinstance(report.get("report"), dict) else None
        return ok, (
            f"suite={suite_id}, cases={len(case_ids)}, health={first_health}, "
            f"audio=skipped_renderer_not_configured, review=synthetic, sign={signed.get('summary', {}).get('status')}, "
            f"report_tamper={tampered.get('summary', {}).get('status')}, signoff_integrity={signoff_check.get('signoff', {}).get('report_integrity', {}).get('status')}, "
            f"missing_midi={missing_health.get('status')}, signed_guard={blocked_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v45_acceptance_profiles_songbook_smoke(root: Path) -> tuple[bool, str]:
    base = (Path(tempfile.gettempdir()) / "mf-v45-acceptance-profiles-songbook").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        profiles_status, profiles = _release_http_json(server, "GET", "/api/acceptance/profiles")
        songbook_status, songbook = _release_http_json(server, "GET", "/api/acceptance/songbook")

        left_status, left_suite = _v45_acceptance_suite(server, "Left", review_mode="manual")
        right_status, right_suite = _v45_acceptance_suite(server, "Right", review_mode="manual")
        left_id = left_suite.get("suite_id")
        right_id = right_suite.get("suite_id")
        diff_status, diff = _release_http_json(server, "POST", f"/api/acceptance/suites/{right_id}/diff", {"other_suite_id": left_id})

        rc_status, rc_suite = _v45_acceptance_suite(server, "RC Synthetic", profile_id="release_candidate", review_mode="synthetic")
        incomplete_rc_status, incomplete_rc_suite = _v45_acceptance_suite(server, "RC Incomplete Manual", profile_id="release_candidate", review_mode="manual")

        project_id = _v37_signed_project(server, "Acceptance Gate Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Acceptance Gate Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        blocked_sign_status, blocked_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "acceptance_suite_id": rc_suite.get("suite_id")})
        incomplete_sign_status, incomplete_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "acceptance_suite_id": incomplete_rc_suite.get("suite_id")})

        profile_ids = {item.get("profile_id") for item in profiles.get("profiles", []) if isinstance(item, dict)}
        song_count = len(songbook.get("songbook", {}).get("songs", []))
        ok = (
            profiles_status == 200
            and {"midi_smoke", "developer_manual", "release_candidate", "audio_required"}.issubset(profile_ids)
            and songbook_status == 200
            and song_count == 12
            and left_status == "passed"
            and right_status == "passed"
            and diff_status == 200
            and diff.get("diff", {}).get("status") == "passed"
            and rc_status == "failed"
            and incomplete_rc_status == "failed"
            and release_status == 201
            and track_status == 200
            and qa_status == 200
            and export_status == 200
            and zip_status == 200
            and blocked_sign_status == 409
            and incomplete_sign_status == 409
            and "Acceptance suite" in str(blocked_sign.get("error") or "")
            and "Acceptance suite" in str(incomplete_sign.get("error") or "")
        )
        return ok, (
            f"profiles={len(profile_ids)}, songs={song_count}, diff={diff.get('diff', {}).get('status')}, "
            f"rc={rc_status}, incomplete_rc={incomplete_rc_status}, release_gate={blocked_sign_status}/{incomplete_sign_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v45_acceptance_suite(server: Any, name: str, *, profile_id: str = "midi_smoke", review_mode: str = "manual") -> tuple[str, dict[str, Any]]:
    create_status, created = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": name, "profile_id": profile_id, "require_audio_if_renderer_configured": False})
    if create_status != 201:
        return "failed", {}
    suite = created.get("suite", {})
    suite_id = suite.get("suite_id")
    song_ids = ["upbeat_pop_001"] if profile_id == "release_candidate" else ["upbeat_pop_001", "sad_ballad_001"]
    for song_id in song_ids:
        case_status, case = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {"song_id": song_id, "request": {"title": song_id, "language": "English", "style": "upbeat pop", "theme": "v4.5 smoke", "duration_seconds": 90}},
        )
        case_id = case.get("case", {}).get("case_id")
        generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        health_status, _health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Acceptance profile smoke review confirms MIDI playback.", "audio_mode": "midi", "review_mode": review_mode},
        )
        if not (case_status == 201 and generate_status == 200 and health_status == 200 and review_status == 200):
            return "failed", suite
    report_status, report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
    if report_status != 200:
        return "failed", suite
    return str(report.get("summary", {}).get("status") or report.get("report", {}).get("status") or "failed"), suite


def _v46_human_review_pack_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v46-human-review-pack-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server
        from song_agent.regression_songbook import list_regression_songs

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        create_status, created = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.6 Human Review", "profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
        suite_id = created.get("suite", {}).get("suite_id")
        case_ids: list[str] = []
        for song in list_regression_songs():
            case_status, case = _release_http_json(
                server,
                "POST",
                f"/api/acceptance/suites/{suite_id}/cases",
                {
                    "name": song.get("title"),
                    "song_id": song.get("song_id"),
                    "songbook_id": song.get("songbook_id"),
                    "songbook_version": song.get("songbook_version"),
                    "expectations": song.get("expectations") or {},
                    "request": song.get("request") or {},
                },
            )
            case_id = case.get("case", {}).get("case_id")
            case_ids.append(case_id)
            generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
            health_status, _health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
            if not (case_status == 201 and generate_status == 200 and health_status == 200):
                raise RuntimeError(f"case prep failed for {song.get('song_id')}: {case_status}/{generate_status}/{health_status}")

        pack_status, pack_response = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/human-review-packs", {})
        pack = pack_response.get("pack", {})
        pack_id = pack.get("pack_id")
        zip_status, zip_response = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/human-review-packs/{pack_id}/zip", {})
        verify_status, verify_response = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/human-review-packs/{pack_id}/verify", {"strict": True})
        zip_path = base / ".musicforge" / "acceptance" / suite_id / "human-review-packs" / pack_id / f"{suite_id}-{pack_id}-human-review-pack.zip"
        external_zip = base / "external-human-review-pack.zip"
        shutil.copy2(zip_path, external_zip)
        external_verify = verify_human_review_pack(external_zip, strict=True)

        song_mismatch = _v46_review_response(pack)
        if song_mismatch.get("reviews"):
            song_mismatch["reviews"][0]["song_id"] = "WRONG_SONG"
        song_mismatch_status, _song_mismatch_response = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/review-imports", {"response": song_mismatch})
        response = _v46_review_response(pack, needs_fix_song_id="rap_beat_001")
        import_status, imported = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/review-imports", {"response": response})
        report_status, report = _release_http_json(server, "GET", f"/api/acceptance/suites/{suite_id}/report")
        pack_after_needs_status, pack_after_needs = _release_http_json(server, "GET", f"/api/acceptance/suites/{suite_id}/human-review-packs/{pack_id}")
        source_path_status, _source_path = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/review-imports", {"source_path": "C:\\Users\\secret\\review-response.json"})
        stale = _v46_review_response(pack)
        stale["pack_source_hash"] = "0" * 64
        stale_status, _stale_response = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/review-imports", {"response": stale})

        accepted_response = _v46_review_response(pack)
        import_all_status, imported_all = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/review-imports", {"response": accepted_response})
        pack_after_all_status, pack_after_all = _release_http_json(server, "GET", f"/api/acceptance/suites/{suite_id}/human-review-packs/{pack_id}")
        report_all_status, report_all = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")

        project_id = _v37_signed_project(server, "Human Review Gate Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Human Review Gate Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_release_status, _zip_release = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "acceptance_suite_id": suite_id})

        tampered_zip = base / "tampered-human-review-pack.zip"
        tamper_source_zip = base / ".musicforge" / "acceptance" / suite_id / "human-review-packs" / pack_id / f"{suite_id}-{pack_id}-human-review-pack.zip"
        with zipfile.ZipFile(tamper_source_zip, "r") as source, zipfile.ZipFile(tampered_zip, "w") as target:
            for info in source.infolist():
                data = source.read(info)
                if info.filename == "index.html":
                    data = data.replace(b"</body>", b'<script src="https://example.com/review.js"></script></body>')
                target.writestr(info.filename, data)
            target.writestr("manifest.json", json.dumps(read_json(base / ".musicforge" / "acceptance" / suite_id / "human-review-packs" / pack_id / "manifest.json")))
            target.writestr("../escape.txt", "bad")
        tampered_verify = verify_human_review_pack(tampered_zip, strict=True)

        serialized_import = json.dumps(imported_all, ensure_ascii=False)
        ok = (
            create_status == 201
            and len(case_ids) == 12
            and pack_status == 201
            and pack.get("case_count") == 12
            and zip_status == 200
            and verify_status == 200
            and verify_response.get("report", {}).get("status") == "passed"
            and external_verify.get("status") == "passed"
            and song_mismatch_status == 400
            and import_status == 201
            and imported.get("summary", {}).get("needs_fix_count") == 1
            and imported.get("summary", {}).get("created_review_task_count") >= 1
            and report_status == 200
            and report.get("summary", {}).get("release_ready") is False
            and pack_after_needs_status == 200
            and pack_after_needs.get("pack", {}).get("stale") is False
            and source_path_status == 400
            and stale_status == 409
            and import_all_status == 201
            and imported_all.get("summary", {}).get("accepted_count") == 12
            and pack_after_all_status == 200
            and pack_after_all.get("pack", {}).get("stale") is False
            and report_all_status == 200
            and report_all.get("summary", {}).get("acceptance_status") == "release_ready_passed"
            and release_status == 201
            and track_status == 200
            and qa_status == 200
            and export_status == 200
            and zip_release_status == 200
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("human_review_pack", {}).get("latest_import_id")
            and tampered_verify.get("status") == "failed"
            and "sk-secret-value" not in serialized_import
            and "C:\\Users" not in serialized_import
        )
        return ok, (
            f"suite={suite_id}, cases={len(case_ids)}, pack={pack_id}, verify={verify_response.get('report', {}).get('status')}, "
            f"needs_fix={imported.get('summary', {}).get('needs_fix_count')}, reimport={import_all_status}, all={report_all.get('summary', {}).get('acceptance_status')}, "
            f"pack_stale={pack_after_needs.get('pack', {}).get('stale')}/{pack_after_all.get('pack', {}).get('stale')}, "
            f"release_sign={sign_status}, tampered={tampered_verify.get('status')}, guards={source_path_status}/{stale_status}, song_mismatch={song_mismatch_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v46_review_response(pack: dict[str, Any], *, needs_fix_song_id: str | None = None) -> dict[str, Any]:
    reviews = []
    for item in pack.get("cases", []):
        if not isinstance(item, dict):
            continue
        needs_fix = bool(needs_fix_song_id and item.get("song_id") == needs_fix_song_id)
        reviews.append(
            {
                "case_id": item.get("case_id"),
                "song_id": item.get("song_id"),
                "status": "needs_fix" if needs_fix else "accepted",
                "rating": 2 if needs_fix else 5,
                "playback_confirmed": True,
                "audio_mode": item.get("audio_mode") or "midi",
                "notes": "Manual human review confirms playback; hook section needs adjustment." if needs_fix else "Manual human review confirms playback and musical quality are acceptable.",
                "issues": ["hook section needs adjustment"] if needs_fix else [],
                "markers": [{"beat": 8, "severity": "warning", "label": "hook", "note": "Needs adjustment"}] if needs_fix else [],
                "tags": ["external-review"],
            }
        )
    return {
        "schema_version": 1,
        "suite_id": pack.get("suite_id"),
        "pack_id": pack.get("pack_id"),
        "pack_source_hash": pack.get("source_hash"),
        "reviewer": {"name": "release-check reviewer", "organization": "MusicForge QA"},
        "reviewed_at": "2026-05-19T00:00:00+00:00",
        "reviews": reviews,
    }


def _v47_acceptance_analytics_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v47-acceptance-analytics-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Acceptance Analytics Track")
        suite_status, created_suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.7 analytics", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = created_suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {
                "name": "Analytics Project Case",
                "source_type": "project_version",
                "project_id": project_id,
                "version_id": "v001",
                "song_id": "rap_beat_001",
                "request": {"title": "Analytics Project Case", "language": "English", "style": "rap beat", "theme": "analytics", "duration_seconds": 90},
            },
        )
        case_id = case.get("case", {}).get("case_id")
        generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        health_status, _health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {
                "rating": 1,
                "status": "rejected",
                "playback_confirmed": True,
                "review_mode": "manual",
                "audio_mode": "midi",
                "notes": "Hook, rhythm, melody, arrangement, mix, structure, and ending all need repair.",
                "tags": ["hook", "rhythm", "melody", "arrangement", "mix", "structure", "ending"],
            },
        )
        report_status, _acceptance_report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        global_status, global_report = _release_http_json(server, "POST", "/api/acceptance/analytics/refresh", {"scope": "global"})
        suite_analytics_status, suite_report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/analytics/refresh")
        report_id = suite_report.get("analytics", {}).get("report_id")
        recommendation_id = next(
            (
                item.get("recommendation_id")
                for item in suite_report.get("analytics", {}).get("recommendations", [])
                if isinstance(item, dict) and item.get("type") == "create_review_task"
            ),
            "",
        )
        task_status, task_response = _release_http_json(server, "POST", f"/api/acceptance/analytics/reports/{report_id}/recommendations/{recommendation_id}/create-review-task", {})
        duplicate_task_status, duplicate_task_response = _release_http_json(server, "POST", f"/api/acceptance/analytics/reports/{report_id}/recommendations/{recommendation_id}/create-review-task", {})

        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Analytics Gate Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        release_analytics_status, release_analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export_response = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        blocked_sign_status, blocked_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check"})
        force_sign_status, force_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "v4.7 analytics blocked smoke"})
        final_manifest = read_json(base / ".musicforge" / "releases" / release_id / "release-export" / "manifest.json")
        analytics_summary_path = base / ".musicforge" / "releases" / release_id / "release-export" / "acceptance-analytics-summary.json"
        analytics_summary = read_json(analytics_summary_path) if analytics_summary_path.exists() else {}

        _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {
                "rating": 5,
                "status": "accepted",
                "playback_confirmed": True,
                "review_mode": "manual",
                "audio_mode": "midi",
                "notes": "Manual reviewer confirms the analytics case has been repaired.",
            },
        )
        stale_status, stale_detail = _release_http_json(server, "GET", f"/api/acceptance/analytics/reports/{report_id}")
        stale_create_status, stale_create = _release_http_json(server, "POST", f"/api/acceptance/analytics/reports/{report_id}/recommendations/{recommendation_id}/create-review-task", {})

        global_heatmap = len(global_report.get("analytics", {}).get("songbook_heatmap", []))
        issue_count = len(suite_report.get("analytics", {}).get("issue_taxonomy", []))
        ok = (
            suite_status == 201
            and case_status == 201
            and generate_status == 200
            and health_status == 200
            and review_status == 200
            and report_status == 200
            and global_status == 201
            and global_heatmap == 12
            and suite_analytics_status == 201
            and suite_report.get("summary", {}).get("readiness_status") == "blocked"
            and issue_count >= 4
            and task_status == 201
            and task_response.get("status") == "created"
            and duplicate_task_status == 200
            and duplicate_task_response.get("status") == "existing"
            and stale_status == 200
            and stale_detail.get("analytics", {}).get("stale") is True
            and stale_create_status == 409
            and "stale" in str(stale_create.get("error") or "").lower()
            and release_status == 201
            and track_status == 200
            and qa_status == 200
            and export_status == 200
            and zip_status == 200
            and release_analytics_status == 201
            and release_analytics.get("summary", {}).get("readiness_status") == "blocked"
            and blocked_sign_status == 409
            and "Acceptance analytics" in str(blocked_sign.get("error") or "")
            and force_sign_status == 200
            and force_sign.get("signoff", {}).get("acceptance_gate", {}).get("acceptance_analytics", {}).get("readiness_status") == "blocked"
            and final_manifest.get("acceptance_analytics", {}).get("readiness_status") == "blocked"
            and analytics_summary.get("readiness_status") == "blocked"
        )
        return ok, (
            f"heatmap={global_heatmap}, issues={issue_count}, readiness={suite_report.get('summary', {}).get('readiness_status')}, "
            f"task={task_status}/{duplicate_task_status}, stale={stale_detail.get('analytics', {}).get('stale')}/{stale_create_status}, "
            f"release_gate={blocked_sign_status}/{force_sign_status}, export_summary={analytics_summary.get('readiness_status')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v48_acceptance_fix_sprint_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v48-acceptance-fix-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Acceptance Fix Sprint Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Acceptance Fix Sprint Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.8 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {
                "name": "Fix Sprint Source Case",
                "source_type": "project_version",
                "project_id": project_id,
                "version_id": "v001",
                "song_id": "rap_beat_001",
                "request": {"title": "Fix Sprint Source", "language": "English", "style": "rap beat", "theme": "fix sprint", "duration_seconds": 90},
            },
        )
        case_id = case.get("case", {}).get("case_id")
        generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        health_status, _health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {
                "rating": 2,
                "status": "needs_fix",
                "playback_confirmed": True,
                "review_mode": "manual",
                "audio_mode": "midi",
                "notes": "Hook, rhythm, workflow, arrangement, and ending need acceptance-driven repair.",
                "tags": ["hook", "rhythm", "workflow", "arrangement", "ending"],
            },
        )
        report_status, _report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        source_report_id = analytics.get("analytics", {}).get("report_id")
        fix_status, fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": source_report_id, "scope": {"type": "release", "release_id": release_id}})
        fix_sprint_id = fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        duplicate_status, duplicate = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Acceptance-driven fix completed."
        write_json(task_path, task)
        refresh_status, refreshed = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        recheck_generate_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        recheck_health_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review",
            {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Recheck confirms the fix."},
        )
        recheck_report_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/delta/refresh")
        close_status, closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/close")
        closeout_status = closeout.get("closeout_report", {}).get("status")
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        force_sign_status, signed = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "v4.8 acceptance fix sprint smoke keeps source analytics blocked", "require_acceptance_fix_sprint": True})
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})

        stale_suite_status, stale_suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.8 stale source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        stale_suite_id = stale_suite.get("suite", {}).get("suite_id")
        stale_case_status, stale_case = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{stale_suite_id}/cases",
            {"song_id": "rock_chorus_001", "request": {"title": "Stale Fix Sprint", "language": "English", "style": "rock chorus", "theme": "stale", "duration_seconds": 90}},
        )
        stale_case_id = stale_case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/cases/{stale_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/cases/{stale_case_id}/health")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/cases/{stale_case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook needs work.", "tags": ["hook"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/report")
        stale_analytics_status, stale_analytics = _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/analytics/refresh")
        stale_fix_status, stale_fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": stale_analytics.get("analytics", {}).get("report_id")})
        stale_fix_id = stale_fix.get("fix_sprint", {}).get("fix_sprint_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{stale_suite_id}/cases/{stale_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Stale guard source changed."})
        stale_guard_status, stale_guard = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{stale_fix_id}/create-review-tasks")
        stale_force_close_status, stale_force_close = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{stale_fix_id}/close", {"force": True, "override_reason": "stale source must block force close"})

        manifest = export.get("manifest", {})
        evidence = signed.get("signoff", {}).get("acceptance_gate", {}).get("acceptance_fix_sprint", {})
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and generate_status == 200
            and health_status == 200
            and review_status == 200
            and report_status == 200
            and analytics_status == 201
            and fix_status == 201
            and tasks_status == 201
            and (tasks.get("results") or [{}])[0].get("status") == "created"
            and duplicate_status == 200
            and (duplicate.get("results") or [{}])[0].get("status") == "existing"
            and refresh_status == 200
            and refreshed.get("summary", {}).get("completed_review_task_count") == 1
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_generate_status == 200
            and recheck_health_status == 200
            and recheck_review_status == 200
            and recheck_report_status == 200
            and delta_status == 200
            and delta.get("summary", {}).get("fixed_item_count") == 1
            and close_status == 200
            and closeout_status == "passed"
            and qa_status == 200
            and export_status == 200
            and manifest.get("acceptance_fix_sprint", {}).get("status") == "closed"
            and force_sign_status == 200
            and evidence.get("status") == "passed"
            and evidence.get("sprint_status") == "closed"
            and project_export_status == 200
            and project_export.get("acceptance_fix_sprint_summary", {}).get("status") == "closed"
            and final_export_status == 200
            and final_export.get("final_export", {}).get("acceptance_fix_sprint", {}).get("status") == "closed"
            and stale_suite_status == 201
            and stale_case_status == 201
            and stale_analytics_status == 201
            and stale_fix_status == 201
            and stale_guard_status == 409
            and "stale" in str(stale_guard.get("error") or "").lower()
            and stale_force_close_status == 409
            and "stale" in str(stale_force_close.get("error") or "").lower()
        )
        return ok, (
            f"sprint={fix_sprint_id}, tasks={tasks_status}/{duplicate_status}, recheck={recheck_suite_id}, "
            f"delta={delta.get('summary', {}).get('status')}, close={closeout_status}, "
            f"export={manifest.get('acceptance_fix_sprint', {}).get('status')}, project={project_export.get('acceptance_fix_sprint_summary', {}).get('status')}, "
            f"final={final_export.get('final_export', {}).get('acceptance_fix_sprint', {}).get('status')}, gate={evidence.get('status')}, "
            f"stale_guard={stale_guard_status}, stale_force_close={stale_force_close_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v49_acceptance_knowledge_base_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v49-acceptance-kb-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Acceptance KB Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Acceptance KB Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.9 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {
                "name": "KB Source Case",
                "source_type": "project_version",
                "project_id": project_id,
                "version_id": "v001",
                "song_id": "rap_beat_001",
                "request": {"title": "KB Source", "language": "English", "style": "rap beat", "theme": "knowledge", "duration_seconds": 90},
            },
        )
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook and rhythm need work with local-path-marker and masked-key-marker.", "tags": ["hook", "rhythm"]},
        )
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        fix_status, fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics.get("analytics", {}).get("report_id"), "scope": {"type": "release", "release_id": release_id}})
        fix_sprint_id = fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Acceptance KB smoke fix resolved hook and rhythm."
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/delta/refresh")
        close_status, closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        entries_status, entries = _release_http_json(server, "GET", "/api/acceptance/kb/entries")
        search_status, search = _release_http_json(server, "GET", "/api/acceptance/kb/search?issue_type=hook")
        recommend_status, recommend = _release_http_json(server, "POST", "/api/acceptance/kb/recommend", {"issue_types": ["hook"], "style": "rap", "song_id": "rap_beat_001"})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        entry_id = (entries.get("entries") or [{}])[0].get("entry_id")
        hide_status, _hidden = _release_http_json(server, "POST", f"/api/acceptance/kb/entries/{entry_id}/hide")
        hide_refresh_status, hide_refresh = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        hide_search_status, hide_search = _release_http_json(server, "GET", "/api/acceptance/kb/search?issue_type=hook")
        include_hidden_status, include_hidden = _release_http_json(server, "GET", "/api/acceptance/kb/search?issue_type=hook&include_hidden=1")

        entry_payload = json.dumps(entries, ensure_ascii=False)
        kb_summary = kb.get("summary", {})
        manifest = export.get("manifest", {})
        recommendation = recommend.get("recommendation", {})
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and fix_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and delta.get("summary", {}).get("status") == "improved"
            and close_status == 200
            and closeout.get("summary", {}).get("status") == "passed"
            and kb_status == 201
            and int(kb_summary.get("entry_count") or 0) >= 1
            and int(kb_summary.get("effective_count") or 0) >= 1
            and entries_status == 200
            and search_status == 200
            and search.get("summary", {}).get("entry_count") >= 1
            and recommend_status == 200
            and recommendation.get("status") == "available"
            and qa_status == 200
            and export_status == 200
            and manifest.get("acceptance_kb", {}).get("entry_count", 0) >= 1
            and any(file.get("path") == "acceptance-kb-summary.json" for file in manifest.get("files", []) if isinstance(file, dict))
            and project_export_status == 200
            and project_export.get("acceptance_kb_summary", {}).get("entry_count", 0) >= 1
            and final_export_status == 200
            and final_export.get("final_export", {}).get("acceptance_kb", {}).get("entry_count", 0) >= 1
            and hide_status == 200
            and hide_refresh_status == 201
            and hide_refresh.get("summary", {}).get("entry_count") == 0
            and hide_search_status == 200
            and hide_search.get("summary", {}).get("entry_count") == 0
            and include_hidden_status == 200
            and include_hidden.get("summary", {}).get("entry_count") == 1
            and "masked-key-marker" not in entry_payload
            and "local-path-marker" not in entry_payload
        )
        return ok, (
            f"entries={kb_summary.get('entry_count')}, effective={kb_summary.get('effective_count')}, "
            f"search={search.get('summary', {}).get('entry_count')}, recommendation={recommendation.get('status')}, "
            f"export={'ok' if manifest.get('acceptance_kb', {}).get('entry_count', 0) >= 1 else 'missing'}, "
            f"hide_refresh={hide_search.get('summary', {}).get('entry_count')}/{include_hidden.get('summary', {}).get('entry_count')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v410_knowledge_assisted_fix_planning_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v410-fix-plan-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Acceptance Fix Plan Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Acceptance Fix Plan Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.10 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"name": "Fix Plan Source Case", "source_type": "project_version", "project_id": project_id, "version_id": "v001", "song_id": "rap_beat_001", "request": {"title": "Fix Plan Source", "language": "English", "style": "rap beat", "theme": "planning", "duration_seconds": 90}})
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook and rhythm need work with local-path-marker and masked-key-marker.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics_report_id = analytics.get("analytics", {}).get("report_id")
        seed_fix_status, seed_fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}})
        seed_sprint_id = seed_fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Acceptance Fix Plan seed fix resolved hook and rhythm."
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
        close_status, closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        kb_report_id = kb.get("knowledge_report", {}).get("report_id")

        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook still needs work.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics2_status, analytics2 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics2_report_id = analytics2.get("analytics", {}).get("report_id")
        plan_status, plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        plan_id = plan.get("fix_plan", {}).get("plan_id")
        preview_status, preview = _release_http_json(server, "POST", "/api/acceptance/fix-plans/recommend", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        sprint_status, sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Knowledge-assisted Fix Sprint"})
        planned_sprint = sprint.get("fix_sprint", {})
        planned_sprint_id = planned_sprint.get("fix_sprint_id")
        duplicate_sprint_status, _duplicate_sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Duplicate Knowledge-assisted Fix Sprint"})
        plan_detail_status, plan_detail = _release_http_json(server, "GET", f"/api/acceptance/fix-plans/{plan_id}")
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "analytics remains blocked in planning smoke", "require_acceptance_fix_plan": True})

        analytics3_status, analytics3 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics3_report_id = analytics3.get("analytics", {}).get("report_id")
        stale_plan_status, stale_plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics3_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        stale_plan_id = stale_plan.get("fix_plan", {}).get("plan_id")
        entries_status, entries = _release_http_json(server, "GET", "/api/acceptance/kb/entries")
        entry_id = (entries.get("entries") or [{}])[0].get("entry_id")
        hide_status, _hidden = _release_http_json(server, "POST", f"/api/acceptance/kb/entries/{entry_id}/hide")
        stale_guard_status, _stale_guard = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{stale_plan_id}/create-fix-sprint")
        hidden_default_status, hidden_default = _release_http_json(server, "POST", "/api/acceptance/fix-plans/recommend", {"analytics_report_id": analytics3_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        hidden_include_status, hidden_include = _release_http_json(server, "POST", "/api/acceptance/fix-plans/recommend", {"analytics_report_id": analytics3_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}, "include_hidden_kb": True})

        plan_payload = json.dumps(plan, ensure_ascii=False)
        manifest = export.get("manifest", {})
        plan_summary = plan.get("summary", {})
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and seed_fix_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and delta.get("summary", {}).get("status") == "improved"
            and close_status == 200
            and closeout.get("summary", {}).get("status") == "passed"
            and kb_status == 201
            and analytics2_status == 201
            and plan_status == 201
            and int(plan_summary.get("planned_item_count") or 0) >= 1
            and int(plan_summary.get("kb_match_count") or 0) >= 1
            and preview_status == 200
            and sprint_status == 201
            and planned_sprint.get("source", {}).get("source_type") == "acceptance_fix_plan"
            and duplicate_sprint_status == 409
            and plan_detail_status == 200
            and plan_detail.get("fix_plan", {}).get("execution", {}).get("created_fix_sprint_id") == planned_sprint_id
            and qa_status == 200
            and export_status == 200
            and manifest.get("acceptance_fix_plan", {}).get("plan_id") == plan_id
            and any(file.get("path") == "acceptance-fix-plan-summary.json" for file in manifest.get("files", []) if isinstance(file, dict))
            and project_export_status == 200
            and project_export.get("acceptance_fix_plan_summary", {}).get("plan_id") == plan_id
            and final_export_status == 200
            and final_export.get("final_export", {}).get("acceptance_fix_plan", {}).get("plan_id") == plan_id
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("acceptance_fix_plan", {}).get("status") == "passed"
            and analytics3_status == 201
            and stale_plan_status == 201
            and entries_status == 200
            and hide_status == 200
            and stale_guard_status == 409
            and hidden_default_status == 200
            and hidden_default.get("summary", {}).get("kb_match_count") == 0
            and hidden_include_status == 200
            and hidden_include.get("summary", {}).get("kb_match_count") >= 1
            and "hidden_entries_included" in hidden_include.get("fix_plan_preview", {}).get("warnings", [])
            and "masked-key-marker" not in plan_payload
            and "local-path-marker" not in plan_payload
        )
        return ok, (
            f"plan={plan_id}, items={plan_summary.get('planned_item_count')}, kb={plan_summary.get('kb_match_count')}, "
            f"sprint={planned_sprint_id}, duplicate={duplicate_sprint_status}, stale_guard={stale_guard_status}, "
            f"hidden={'excluded' if hidden_default.get('summary', {}).get('kb_match_count') == 0 else 'included'}/"
            f"{'included' if hidden_include.get('summary', {}).get('kb_match_count', 0) >= 1 else 'excluded'}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v411_fix_plan_outcome_review_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v411-plan-review-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Fix Plan Outcome Review Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Fix Plan Outcome Review Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.11 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"name": "Outcome Source Case", "source_type": "project_version", "project_id": project_id, "version_id": "v001", "song_id": "rap_beat_001", "request": {"title": "Outcome Source", "language": "English", "style": "rap beat", "theme": "outcome", "duration_seconds": 90}})
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook and rhythm need work with local-path-marker and masked-key-marker.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics_report_id = analytics.get("analytics", {}).get("report_id")
        seed_fix_status, seed_fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}})
        seed_sprint_id = seed_fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Outcome review seed fix resolved hook and rhythm."
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
        close_status, closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        kb_report_id = kb.get("knowledge_report", {}).get("report_id")

        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook still needs work.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics2_status, analytics2 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics2_report_id = analytics2.get("analytics", {}).get("report_id")
        plan_status, plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        plan_id = plan.get("fix_plan", {}).get("plan_id")
        sprint_status, sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Outcome Review Sprint"})
        planned_sprint_id = sprint.get("fix_sprint", {}).get("fix_sprint_id")
        planned_item_id = (sprint.get("items") or [{}])[0].get("item_id")
        waive_status, _waive = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/items/{planned_item_id}/waive", {"reason": "manual rewrite verified"})
        planned_recheck_status, planned_recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        planned_suite_id = planned_recheck.get("suite", {}).get("suite_id")
        planned_detail_status, planned_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{planned_suite_id}")
        planned_case_id = (planned_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/health")
        planned_review_status, _planned_review = _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "synthetic", "audio_mode": "midi", "notes": "Synthetic planned recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/report")
        planned_delta_status, planned_delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/delta/refresh")
        planned_close_status, planned_closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
        review_refresh_status, review = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = review.get("outcome_review", {}).get("review_id")
        review_summary = review.get("summary", {})
        review_list_status, review_list = _release_http_json(server, "GET", "/api/acceptance/fix-plan-reviews")
        review_detail_status, review_detail = _release_http_json(server, "GET", f"/api/acceptance/fix-plan-reviews/{review_id}")

        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "analytics remains blocked in outcome review smoke", "require_acceptance_fix_plan_review": True, "acceptance_fix_plan_review_id": review_id})
        reset_status, _reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify stale outcome review gate"})

        delta_path = base / ".musicforge" / "acceptance-fix-sprints" / str(planned_sprint_id) / "delta-report.json"
        polluted_delta = read_json(delta_path)
        polluted_delta["summary"]["rating_delta"] = -9
        write_json(delta_path, polluted_delta)
        stale_get_status, stale_get = _release_http_json(server, "GET", f"/api/acceptance/fix-plan-reviews/{review_id}")
        stale_sign_status, stale_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_acceptance_fix_plan_review": True, "acceptance_fix_plan_review_id": review_id})

        review_payload = json.dumps(review, ensure_ascii=False)
        manifest = export.get("manifest", {})
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and seed_fix_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and close_status == 200
            and closeout.get("summary", {}).get("status") == "passed"
            and kb_status == 201
            and analytics2_status == 201
            and plan_status == 201
            and sprint_status == 201
            and waive_status == 200
            and planned_recheck_status == 201
            and planned_detail_status == 200
            and planned_review_status == 200
            and planned_delta_status == 200
            and planned_close_status == 200
            and planned_closeout.get("summary", {}).get("status") in {"passed", "force_closed"}
            and review_refresh_status == 201
            and review_summary.get("review_id") == review_id
            and int(review_summary.get("plan_effectiveness_score") or 0) > 0
            and review_summary.get("kb_evidence_helpfulness") not in {"missing", None}
            and review_summary.get("manual_recheck_confirmed") is False
            and review_summary.get("synthetic_only") is True
            and "synthetic_only_recheck" in review.get("outcome_review", {}).get("warnings", [])
            and (review.get("outcome_review", {}).get("item_outcomes") or [{}])[0].get("planned_item_id") == "afpi-000001"
            and review_list_status == 200
            and int(review_list.get("summary", {}).get("review_count") or 0) >= 1
            and review_detail_status == 200
            and qa_status == 200
            and export_status == 200
            and manifest.get("acceptance_fix_plan_review", {}).get("review_id") == review_id
            and any(file.get("path") == "acceptance-fix-plan-review-summary.json" for file in manifest.get("files", []) if isinstance(file, dict))
            and project_export_status == 200
            and project_export.get("acceptance_fix_plan_review_summary", {}).get("review_id") == review_id
            and final_export_status == 200
            and final_export.get("final_export", {}).get("acceptance_fix_plan_review", {}).get("review_id") == review_id
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("acceptance_fix_plan_review", {}).get("status") == "passed"
            and reset_status == 200
            and stale_get_status == 200
            and stale_get.get("summary", {}).get("stale") is True
            and stale_sign_status == 409
            and "masked-key-marker" not in review_payload
            and "local-path-marker" not in review_payload
        )
        return ok, (
            f"review={review_id}, effectiveness={review_summary.get('plan_effectiveness_score')}, "
            f"helpfulness={review_summary.get('kb_evidence_helpfulness')}, manual={review_summary.get('manual_recheck_confirmed')}, "
            f"synthetic_only={review_summary.get('synthetic_only')}, stale_guard={stale_sign_status}, "
            f"signoff={signoff.get('signoff', {}).get('acceptance_gate', {}).get('acceptance_fix_plan_review', {}).get('status')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v412_planning_rule_simulation_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v412-planning-sim-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Planning Rule Simulation Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Planning Rule Simulation Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.12 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"name": "Planning Source Case", "source_type": "project_version", "project_id": project_id, "version_id": "v001", "song_id": "rap_beat_001", "request": {"title": "Planning Source", "language": "English", "style": "rap beat", "theme": "planning", "duration_seconds": 90}})
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook and rhythm need work with local-path-marker and masked-key-marker.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics_report_id = analytics.get("analytics", {}).get("report_id")
        seed_fix_status, seed_fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}})
        seed_sprint_id = seed_fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Planning simulation seed fix resolved hook and rhythm."
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual seed recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, _delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
        close_status, _closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        kb_report_id = kb.get("knowledge_report", {}).get("report_id")

        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Hook still needs work.", "tags": ["hook", "rhythm"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics2_status, analytics2 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics2_report_id = analytics2.get("analytics", {}).get("report_id")
        plan_status, plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        plan_id = plan.get("fix_plan", {}).get("plan_id")
        sprint_status, sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Planning Simulation Sprint"})
        planned_sprint_id = sprint.get("fix_sprint", {}).get("fix_sprint_id")
        planned_item_id = (sprint.get("items") or [{}])[0].get("item_id")
        waive_status, _waive = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/items/{planned_item_id}/waive", {"reason": "manual rewrite verified"})
        planned_recheck_status, planned_recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        planned_suite_id = planned_recheck.get("suite", {}).get("suite_id")
        planned_detail_status, planned_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{planned_suite_id}")
        planned_case_id = (planned_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/health")
        planned_review_status, _planned_review = _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "synthetic", "audio_mode": "midi", "notes": "Synthetic planned recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/report")
        planned_delta_status, planned_delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/delta/refresh")
        planned_close_status, planned_closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
        review_refresh_status, review = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = review.get("outcome_review", {}).get("review_id")
        review_summary = review.get("summary", {})

        ruleset_status, ruleset = _release_http_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict", "description": "Synthetic strict local-path-marker masked-key-marker"})
        ruleset_id = ruleset.get("ruleset", {}).get("ruleset_id")
        simulation_status, simulation = _release_http_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "release", "release_id": release_id}, "review_ids": [review_id]})
        simulation_id = simulation.get("simulation", {}).get("simulation_id")
        simulation_summary = simulation.get("summary", {})
        item = (((simulation.get("simulation", {}).get("review_results") or [{}])[0].get("item_results") or [{}])[0])

        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "analytics remains warning in planning simulation smoke", "require_planning_rule_simulation": True, "planning_simulation_id": simulation_id})
        reset_status, _reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify stale planning simulation gate"})

        delta_path = base / ".musicforge" / "acceptance-fix-sprints" / str(planned_sprint_id) / "delta-report.json"
        polluted_delta = read_json(delta_path)
        polluted_delta["summary"]["rating_delta"] = -9
        write_json(delta_path, polluted_delta)
        stale_get_status, stale_get = _release_http_json(server, "GET", f"/api/acceptance/planning-simulations/{simulation_id}")
        stale_sign_status, stale_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_planning_rule_simulation": True, "planning_simulation_id": simulation_id})

        payload_text = json.dumps({"simulation": simulation, "export": export, "project_export": project_export, "final_export": final_export}, ensure_ascii=False)
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and seed_fix_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and close_status == 200
            and kb_status == 201
            and analytics2_status == 201
            and plan_status == 201
            and sprint_status == 201
            and waive_status == 200
            and planned_recheck_status == 201
            and planned_detail_status == 200
            and planned_review_status == 200
            and planned_delta_status == 200
            and planned_close_status == 200
            and planned_closeout.get("summary", {}).get("status") in {"passed", "force_closed"}
            and review_refresh_status == 201
            and review_summary.get("manual_recheck_confirmed") is False
            and review_summary.get("synthetic_only") is True
            and ruleset_status == 201
            and simulation_status == 201
            and item.get("simulated_planning_score", 0) < item.get("baseline_planning_score", 0)
            and simulation_summary.get("synthetic_penalty_applied_count", 0) >= 1
            and qa_status == 200
            and export_status == 200
            and export.get("manifest", {}).get("planning_rule_simulation", {}).get("simulation_id") == simulation_id
            and project_export_status == 200
            and project_export.get("planning_rule_simulation_summary", {}).get("simulation_id") == simulation_id
            and final_export_status == 200
            and final_export.get("final_export", {}).get("planning_rule_simulation", {}).get("simulation_id") == simulation_id
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("planning_rule_simulation", {}).get("status") == "passed"
            and reset_status == 200
            and stale_get_status == 200
            and stale_get.get("summary", {}).get("stale") is True
            and stale_sign_status == 409
            and "masked-key-marker" not in payload_text
            and "local-path-marker" not in payload_text
        )
        return ok, (
            f"ruleset={ruleset_id}, simulation={simulation_id}, delta={item.get('score_delta')}, "
            f"synthetic={simulation_summary.get('synthetic_penalty_applied_count')}, stale_guard={stale_sign_status}, "
            f"signoff={signoff.get('signoff', {}).get('acceptance_gate', {}).get('planning_rule_simulation', {}).get('status')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v413_planning_rule_governance_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v413-rule-gov-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Planning Rule Governance Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Planning Rule Governance Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        missing_status, _missing = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_planning_rule_governance": True})

        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.13 source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"name": "Governance Source Case", "source_type": "project_version", "project_id": project_id, "version_id": "v001", "song_id": "governance_001", "request": {"title": "Governance Source", "language": "English", "style": "rap beat", "theme": "governance", "duration_seconds": 90}})
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Governance issue needs fix.", "tags": ["hook"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics_report_id = analytics.get("analytics", {}).get("report_id")
        seed_fix_status, seed_fix = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}})
        seed_sprint_id = seed_fix.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Governance seed resolved."
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        recheck_detail_status, recheck_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (recheck_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, _delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
        close_status, _closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        kb_report_id = kb.get("knowledge_report", {}).get("report_id")

        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Governance still needs work.", "tags": ["hook"]})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics2_status, analytics2 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics2_report_id = analytics2.get("analytics", {}).get("report_id")
        legacy_plan_status, legacy_plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        legacy_governance = legacy_plan.get("fix_plan", {}).get("source", {}).get("planning_rule_governance", {})
        plan_id = legacy_plan.get("fix_plan", {}).get("plan_id")
        sprint_status, sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Planning Governance Sprint"})
        planned_sprint_id = sprint.get("fix_sprint", {}).get("fix_sprint_id")
        planned_item_id = (sprint.get("items") or [{}])[0].get("item_id")
        waive_status, _waive = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/items/{planned_item_id}/waive", {"reason": "manual governance verification"})
        planned_recheck_status, planned_recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        planned_suite_id = planned_recheck.get("suite", {}).get("suite_id")
        planned_detail_status, planned_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{planned_suite_id}")
        planned_case_id = (planned_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/health")
        planned_review_status, _planned_review = _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "synthetic", "audio_mode": "midi", "notes": "Synthetic governance recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/report")
        planned_delta_status, _planned_delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/delta/refresh")
        planned_close_status, _planned_closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
        review_refresh_status, review = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = review.get("outcome_review", {}).get("review_id")

        ruleset_status, ruleset = _release_http_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict", "description": "Governance strict local-path-marker masked-key-marker"})
        ruleset_id = ruleset.get("ruleset", {}).get("ruleset_id")
        simulation_status, simulation = _release_http_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "release", "release_id": release_id}, "review_ids": [review_id]})
        simulation_id = simulation.get("simulation", {}).get("simulation_id")
        promotion_status, promotion = _release_http_json(server, "POST", "/api/acceptance/planning-rule-governance/promotions", {"ruleset_id": ruleset_id, "simulation_id": simulation_id, "note": "Governance candidate"})
        promotion_id = promotion.get("promotion", {}).get("promotion_id")
        approve_status, _approved = _release_http_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/approve", {"approved_by": "release-check", "approval_note": "Governance evidence accepted"})
        promote_status, promoted = _release_http_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/promote", {"promoted_by": "release-check"})
        version_id = promoted.get("version", {}).get("version_id")
        active_status, active = _release_http_json(server, "GET", "/api/acceptance/planning-rule-governance/active")

        governed_plan_status, governed_plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        governed_source = governed_plan.get("fix_plan", {}).get("source", {}).get("planning_rule_governance", {})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "analytics remains warning in governance smoke", "require_planning_rule_governance": True, "planning_rule_version_id": version_id})
        reset_status, _reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify stale governance gate"})

        version_path = base / ".musicforge" / "planning-rule-governance" / "versions" / str(version_id) / "version.json"
        original_version = read_json(version_path)
        polluted_version = json.loads(json.dumps(original_version))
        polluted_version["promoted_from"]["recommendation"] = "candidate_better_tampered"
        polluted_version["approval"]["approved_by"] = "tampered-reviewer"
        write_json(version_path, polluted_version)
        tampered_version_status, _tampered_version = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_planning_rule_governance": True, "planning_rule_version_id": version_id})
        write_json(version_path, original_version)

        delta_path = base / ".musicforge" / "acceptance-fix-sprints" / str(planned_sprint_id) / "delta-report.json"
        polluted_delta = read_json(delta_path)
        polluted_delta["summary"]["rating_delta"] = -9
        write_json(delta_path, polluted_delta)
        stale_sign_status, _stale_sign = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_planning_rule_governance": True, "planning_rule_version_id": version_id})
        rollback_status, rollback = _release_http_json(server, "POST", "/api/acceptance/planning-rule-governance/rollback", {"target_version_id": version_id, "reason": "release-check rollback"})

        payload_text = json.dumps({"promotion": promotion, "active": active, "export": export, "project_export": project_export, "final_export": final_export}, ensure_ascii=False)
        ok = (
            release_status == 201
            and track_status == 200
            and missing_status == 409
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and seed_fix_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and recheck_detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and close_status == 200
            and kb_status == 201
            and analytics2_status == 201
            and legacy_plan_status == 201
            and legacy_governance.get("governance_status") == "legacy_default"
            and sprint_status == 201
            and waive_status == 200
            and planned_recheck_status == 201
            and planned_detail_status == 200
            and planned_review_status == 200
            and planned_delta_status == 200
            and planned_close_status == 200
            and review_refresh_status == 201
            and ruleset_status == 201
            and simulation_status == 201
            and promotion_status == 201
            and approve_status == 200
            and promote_status == 201
            and active_status == 200
            and active.get("summary", {}).get("active_version_id") == version_id
            and governed_plan_status == 201
            and governed_source.get("planning_rule_version_id") == version_id
            and qa_status == 200
            and export_status == 200
            and export.get("manifest", {}).get("planning_rule_governance", {}).get("active_version_id") == version_id
            and project_export_status == 200
            and project_export.get("planning_rule_governance_summary", {}).get("active_version_id") == version_id
            and final_export_status == 200
            and final_export.get("final_export", {}).get("planning_rule_governance", {}).get("active_version_id") == version_id
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("planning_rule_governance", {}).get("status") == "passed"
            and reset_status == 200
            and tampered_version_status == 409
            and stale_sign_status == 409
            and rollback_status == 200
            and rollback.get("summary", {}).get("active_version_id") == version_id
            and "masked-key-marker" not in payload_text
            and "local-path-marker" not in payload_text
        )
        return ok, (
            f"promotion={promotion_id}, version={version_id}, active={active.get('summary', {}).get('active_version_id')}, "
            f"plan_rule={governed_source.get('planning_rule_version_id')}, signoff={signoff.get('signoff', {}).get('acceptance_gate', {}).get('planning_rule_governance', {}).get('status')}, "
            f"stale_guard={stale_sign_status}, tampered_version={tampered_version_status}, rollback=passed"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v414_planning_rule_impact_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v414-rule-impact-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        project_id = _v37_signed_project(server, "Planning Rule Impact Track")
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "Planning Rule Impact Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})

        suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v4.14 impact source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
        suite_id = suite.get("suite", {}).get("suite_id")
        case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"name": "Impact Source Case", "source_type": "project_version", "project_id": project_id, "version_id": "v001", "song_id": "impact_001", "request": {"title": "Impact Source", "language": "English", "style": "rap beat", "theme": "impact", "duration_seconds": 90}})
        case_id = case.get("case", {}).get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 2, "status": "needs_fix", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Impact issue needs fix."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        analytics_status, analytics = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics_report_id = analytics.get("analytics", {}).get("report_id")
        seed_status, seed = _release_http_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}})
        seed_sprint_id = seed.get("fix_sprint", {}).get("fix_sprint_id")
        tasks_status, tasks = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-review-tasks")
        task_id = (tasks.get("results") or [{}])[0].get("task_id")
        task_path = base / ".musicforge" / "projects" / project_id / "review-tasks" / str(task_id) / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        write_json(task_path, task)
        _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/refresh-status")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck.get("suite", {}).get("suite_id")
        detail_status, detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = (detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        recheck_review_status, _ = _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, _delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
        close_status, _closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close")
        kb_status, kb = _release_http_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        kb_report_id = kb.get("knowledge_report", {}).get("report_id")

        analytics2_status, analytics2 = _release_http_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        analytics2_report_id = analytics2.get("analytics", {}).get("report_id")
        legacy_plan_status, legacy_plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        legacy_governance = legacy_plan.get("fix_plan", {}).get("source", {}).get("planning_rule_governance", {})
        legacy_plan_id = legacy_plan.get("fix_plan", {}).get("plan_id")
        sprint_status, sprint = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{legacy_plan_id}/create-fix-sprint", {"name": "Impact Legacy Sprint"})
        planned_sprint_id = sprint.get("fix_sprint", {}).get("fix_sprint_id")
        planned_item_id = (sprint.get("items") or [{}])[0].get("item_id")
        waive_status, _waive = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/items/{planned_item_id}/waive", {"reason": "manual impact verification"})
        planned_recheck_status, planned_recheck = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        planned_suite_id = planned_recheck.get("suite", {}).get("suite_id")
        planned_detail_status, planned_detail = _release_http_json(server, "GET", f"/api/acceptance/suites/{planned_suite_id}")
        planned_case_id = (planned_detail.get("cases") or [{}])[0].get("case_id")
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/generate", {"render_audio": "never"})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/health")
        planned_review_status, _planned_review = _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual legacy recheck accepted."})
        _release_http_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/report")
        planned_delta_status, _planned_delta = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/delta/refresh")
        planned_close_status, _planned_closeout = _release_http_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/close", {"force": True, "override_reason": "waived issue was verified"})
        review_refresh_status, review = _release_http_json(server, "POST", f"/api/acceptance/fix-plans/{legacy_plan_id}/outcome-review/refresh")
        review_id = review.get("outcome_review", {}).get("review_id")

        ruleset_status, ruleset = _release_http_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict", "description": "Impact strict local-path-marker masked-key-marker"})
        ruleset_id = ruleset.get("ruleset", {}).get("ruleset_id")
        simulation_status, simulation = _release_http_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "release", "release_id": release_id}, "review_ids": [review_id]})
        simulation_id = simulation.get("simulation", {}).get("simulation_id")
        promotion_status, promotion = _release_http_json(server, "POST", "/api/acceptance/planning-rule-governance/promotions", {"ruleset_id": ruleset_id, "simulation_id": simulation_id, "note": "Impact candidate"})
        promotion_id = promotion.get("promotion", {}).get("promotion_id")
        approve_status, _approved = _release_http_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/approve", {"approved_by": "release-check", "approval_note": "Impact evidence accepted"})
        promote_status, promoted = _release_http_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/promote", {"promoted_by": "release-check"})
        version_id = promoted.get("version", {}).get("version_id")

        governed_plan_status, governed_plan = _release_http_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2_report_id, "kb_report_id": kb_report_id, "scope": {"type": "release", "release_id": release_id}})
        governed_source = governed_plan.get("fix_plan", {}).get("source", {}).get("planning_rule_governance", {})
        impact_status, impact = _release_http_json(server, "POST", "/api/acceptance/planning-rule-impact/reports", {"scope": {"type": "release", "release_id": release_id}, "include_legacy": True, "include_superseded": True})
        report_id = impact.get("impact_report", {}).get("report_id")
        impact_summary = impact.get("summary", {})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "impact remains warning in smoke", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        reset_status, _reset = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify impact stale guard"})

        report_path = base / ".musicforge" / "planning-rule-impact" / "reports" / str(report_id) / "report.json"
        report_doc = read_json(report_path)
        report_doc["summary"]["recommendation"] = "rollback_recommended"
        report_doc["summary"]["rollback_recommended"] = True
        report_doc["status"] = "warning"
        write_json(report_path, report_doc)
        tampered_report_status, _tampered_report = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "cannot force tampered impact", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})

        impact_refresh_status, impact_refresh = _release_http_json(server, "POST", f"/api/acceptance/planning-rule-impact/reports/{report_id}/refresh")
        refreshed_report_doc = read_json(report_path)
        refreshed_report_doc["summary"]["recommendation"] = "rollback_recommended"
        refreshed_report_doc["summary"]["rollback_recommended"] = True
        refreshed_report_doc["status"] = "warning"
        refreshed_report_doc["integrity_hash"] = stable_hash({key: refreshed_report_doc.get(key) for key in ("status", "scope", "active_version", "source", "summary", "adoption", "before_after", "risk_drift", "version_metrics", "plan_samples", "review_samples", "warnings")})
        write_json(report_path, refreshed_report_doc)
        rollback_watch_status, _rollback_watch = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        rollback_force_status, _rollback_force = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "manual impact override", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify impact stale hard guard"})

        delta_path = base / ".musicforge" / "acceptance-fix-sprints" / str(planned_sprint_id) / "delta-report.json"
        polluted_delta = read_json(delta_path)
        polluted_delta["summary"]["rating_delta"] = -9
        write_json(delta_path, polluted_delta)
        stale_guard_status, _stale_guard = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "force": True, "override_reason": "cannot force stale impact", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})

        payload_text = json.dumps({"impact": impact, "export": export, "project_export": project_export, "final_export": final_export}, ensure_ascii=False)
        ok = (
            release_status == 201
            and track_status == 200
            and suite_status == 201
            and case_status == 201
            and review_status == 200
            and analytics_status == 201
            and seed_status == 201
            and tasks_status == 201
            and recheck_status == 201
            and detail_status == 200
            and recheck_review_status == 200
            and delta_status == 200
            and close_status == 200
            and kb_status == 201
            and analytics2_status == 201
            and legacy_plan_status == 201
            and legacy_governance.get("governance_status") == "legacy_default"
            and sprint_status == 201
            and waive_status == 200
            and planned_recheck_status == 201
            and planned_detail_status == 200
            and planned_review_status == 200
            and planned_delta_status == 200
            and planned_close_status == 200
            and review_refresh_status == 201
            and ruleset_status == 201
            and simulation_status == 201
            and promotion_status == 201
            and approve_status == 200
            and promote_status == 201
            and governed_plan_status == 201
            and governed_source.get("planning_rule_version_id") == version_id
            and impact_status == 201
            and impact_summary.get("active_version_id") == version_id
            and int(impact_summary.get("observed_plan_count") or 0) >= 2
            and qa_status == 200
            and export_status == 200
            and export.get("manifest", {}).get("planning_rule_impact", {}).get("report_id") == report_id
            and project_export_status == 200
            and project_export.get("planning_rule_impact_summary", {}).get("report_id") == report_id
            and final_export_status == 200
            and final_export.get("final_export", {}).get("planning_rule_impact", {}).get("report_id") == report_id
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("planning_rule_impact", {}).get("status") in {"passed", "warning"}
            and reset_status == 200
            and tampered_report_status == 409
            and impact_refresh_status == 200
            and impact_refresh.get("summary", {}).get("integrity_ok") is True
            and rollback_watch_status == 409
            and rollback_force_status == 200
            and stale_guard_status == 409
            and "masked-key-marker" not in payload_text
            and "local-path-marker" not in payload_text
        )
        return ok, (
            f"report={report_id}, active={version_id}, plans={impact_summary.get('observed_plan_count')}, "
            f"reviews={impact_summary.get('observed_review_count')}, recommendation={impact_summary.get('recommendation')}, "
            f"signoff={signoff.get('signoff', {}).get('acceptance_gate', {}).get('planning_rule_impact', {}).get('status')}, "
            f"tampered_report={tampered_report_status}, stale_guard={stale_guard_status}, rollback_watch={rollback_watch_status}/{rollback_force_status}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v50_real_audio_baseline_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v50-real-audio-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        project_id = _v37_signed_project(server, "v5 Real Audio Track")
        _v50_add_project_audio(server, project_id, duration_seconds=30)
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "v5 Real Audio Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release.get("release", {}).get("release_id")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        refresh_track_status, _refresh_track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks/track-000001/refresh")
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        missing_project = _v37_signed_project(server, "v5 Missing Audio Track")
        missing_release_status, missing_release = _release_http_json(server, "POST", "/api/releases", {"name": "v5 Missing Audio Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        missing_release_id = missing_release.get("release", {}).get("release_id")
        _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/tracks", {"project_id": missing_project})
        _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/qa/refresh")
        missing_audio_status, missing_audio = _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/audio-qa", {"require_audio": True})
        missing_sign_status, _missing_sign = _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True})

        audio_status, audio = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        export_status, _export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        suite_id = _v50_manual_wav_acceptance_suite(server)
        human_missing_status, _human_missing = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True, "require_human_audio_review": True})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "acceptance_suite_id": suite_id, "require_audio_health": True, "require_human_audio_review": True})
        zip_path = base / ".musicforge" / "releases" / str(release_id) / "release-export.zip"
        external = base / "external"
        external.mkdir()
        external_zip = external / "release-export.zip"
        shutil.copy2(zip_path, external_zip)
        verify = verify_release_zip(external_zip, require_audio=True, require_human_review=True)

        ok = (
            release_status == 201
            and track_status == 200
            and refresh_track_status == 200
            and qa_status == 200
            and missing_audio_status == 200
            and missing_audio.get("summary", {}).get("status") == "failed"
            and missing_sign_status == 409
            and audio_status == 200
            and audio.get("summary", {}).get("status") == "passed"
            and export_status == 200
            and zip_status == 200
            and human_missing_status == 409
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("audio", {}).get("status") == "passed"
            and verify.get("status") in {"passed", "warning"}
            and _v38_check_status(verify, "human_audio_review_evidence") == "passed"
        )
        return ok, (
            f"audio={audio.get('summary', {}).get('status')}, missing_audio={missing_audio.get('summary', {}).get('status')}, "
            f"missing_sign={missing_sign_status}, human_missing={human_missing_status}, sign={sign_status}, verify={verify.get('status')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v50_add_project_audio(server: Any, project_id: str, *, duration_seconds: float = 30) -> None:
    project_dir = Path(".musicforge") / "projects" / project_id
    versions = read_json(project_dir / "versions.json")
    output_dir = Path(versions["versions"][0]["output_dir"])
    _v50_write_test_wav(output_dir / "renders" / "song.wav", duration_seconds=duration_seconds)
    manifest = build_audio_artifact_manifest(
        artifact_id=f"project-{project_id}-v001",
        scope="project_version",
        wav_path=output_dir / "renders" / "song.wav",
        midi_path=output_dir / "renders" / "song.mid",
        song_plan_path=output_dir / "data" / "song-plan.json",
        renderer_config=RendererConfig(soundfont_path="fixture.sf2"),
        extra_source={"project_id": project_id, "version_id": "v001"},
    )
    write_audio_artifact_manifest(output_dir / "renders" / "audio-artifact.json", manifest)
    export_status, _export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False, "include_audio": True, "force": True})
    zip_status, _zip = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
    qa_status, _qa = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
    reset_status, _reset = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "v5 audio fixture"})
    sign_status, _sign = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "release-check"})
    if not (export_status == 200 and zip_status == 200 and qa_status == 200 and reset_status == 200 and sign_status == 200):
        raise RuntimeError(f"audio project refresh failed export={export_status} zip={zip_status} qa={qa_status} reset={reset_status} sign={sign_status}")


def _v50_manual_wav_acceptance_suite(server: Any) -> str:
    suite_status, suite = _release_http_json(server, "POST", "/api/acceptance/suites", {"name": "v5 Manual WAV Evidence", "profile_id": "developer_manual", "require_manual_review": True})
    if suite_status != 201:
        raise RuntimeError(f"acceptance suite failed: {suite_status} {suite}")
    suite_id = str(suite.get("suite", {}).get("suite_id") or "")
    case_status, case = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", {"request": {"title": "v5 Manual WAV", "language": "English", "style": "pop", "theme": "real audio", "duration_seconds": 30}})
    case_id = str(case.get("case", {}).get("case_id") or "")
    generate_status, _generated = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
    _v50_write_test_wav(Path(".musicforge") / "acceptance" / suite_id / "cases" / case_id / "song.wav", duration_seconds=30)
    health_status, _health = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
    review_status, _review = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "review_mode": "manual", "audio_mode": "wav", "notes": "Manual WAV listening review confirms real audio playback."})
    report_status, report = _release_http_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
    if not (case_status == 201 and generate_status == 200 and health_status == 200 and review_status == 200 and report_status == 200 and report.get("summary", {}).get("manual_audio_accepted_count") == 1):
        raise RuntimeError(f"manual wav acceptance failed case={case_status} gen={generate_status} health={health_status} review={review_status} report={report_status}")
    return suite_id


def _v50_write_test_wav(path: Path, *, duration_seconds: float = 30.0, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(int(duration_seconds * sample_rate)):
            sample = int(0.25 * 32767 * __import__("math").sin(2 * __import__("math").pi * 440 * index / sample_rate))
            frame = struct.pack("<hh", sample, sample)
            wav.writeframesraw(frame)


def _v51_per_track_audio_review_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v51-audio-review-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        first_project = _v37_signed_project(server, "v5.1 Audio Review One")
        second_project = _v37_signed_project(server, "v5.1 Audio Review Two")
        _v50_add_project_audio(server, first_project, duration_seconds=30)
        _v50_add_project_audio(server, second_project, duration_seconds=30)
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.1 Audio Review Release", "release_type": "ep", "primary_artist": "MusicForge"})
        release_id = str(release.get("release", {}).get("release_id") or "")
        first_track_status, _first_track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        second_track_status, _second_track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        first_review_status, first_review = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual first track accepted.", "markers": [{"time_seconds": 2.0, "category": "mix_balance", "message": "kick balance"}]})
        first_review_id = first_review.get("review", {}).get("review_id")
        missing_gate_status, _missing_gate = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True, "require_per_track_audio_review": True})
        synthetic_status, _synthetic = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000002", "status": "accepted", "review_mode": "synthetic", "rating": 5, "playback_confirmed": True, "notes": "Synthetic does not satisfy release gate."})
        synthetic_gate_status, _synthetic_gate = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True, "require_per_track_audio_review": True})
        second_review_status, second_review = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000002", "status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "Manual second track accepted."})
        summary_status, summary = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/refresh-summary")
        task_status, task = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{first_review_id}/markers/m-000001/create-review-task", {"title": "Review kick balance"})
        duplicate_task_status, duplicate_task = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{first_review_id}/markers/m-000001/create-review-task", {"title": "Review kick balance again"})
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True, "require_human_audio_review": True, "require_per_track_audio_review": True})
        zip_path = base / ".musicforge" / "releases" / release_id / "release-export.zip"
        external_dir = base / "external-verify"
        external_dir.mkdir(parents=True, exist_ok=True)
        external_zip = external_dir / "release-export.zip"
        shutil.copy2(zip_path, external_zip)
        verify = verify_release_zip(external_zip, require_audio=True, require_human_review=True)

        review_name = ""
        with zipfile.ZipFile(zip_path, "r") as archive:
            review_name = next(name for name in archive.namelist() if name.startswith("audio-reviews/reviews/") and str(second_review.get("review", {}).get("review_id")) in name)

        def tamper_review_sha(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            payload["audio_evidence"]["wav_sha256"] = "0" * 64
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def pollute_review_notes(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            payload["notes"] = r"Manual review leaked C:\Users\demo\secret.wav api_key=sk-secret-value"
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        tampered = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-release-review.zip", transforms={review_name: tamper_review_sha}), require_audio=True, require_human_review=True)
        redaction = verify_release_zip(_v38_rewrite_zip(zip_path, base / "polluted-release-review.zip", transforms={review_name: pollute_review_notes}), require_audio=True, require_human_review=True)
        ok = (
            release_status == 201
            and first_track_status == 200
            and second_track_status == 200
            and qa_status == 200
            and audio_status == 200
            and audio.get("summary", {}).get("status") == "passed"
            and first_review_status == 201
            and missing_gate_status == 409
            and synthetic_status == 201
            and synthetic_gate_status == 409
            and second_review_status == 201
            and summary_status == 200
            and summary.get("summary", {}).get("status") == "passed"
            and task_status == 201
            and duplicate_task_status == 200
            and duplicate_task.get("status") == "existing"
            and export_status == 200
            and export.get("manifest", {}).get("audio_reviews", {}).get("status") == "passed"
            and zip_status == 200
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("audio", {}).get("per_track_review", {}).get("manual_accepted_track_count") == 2
            and verify.get("status") in {"passed", "warning"}
            and _v38_check_status(verify, "per_track_audio_review_evidence") == "passed"
            and tampered.get("status") == "failed"
            and _v38_check_status(tampered, "audio_review_payload_hash") == "failed"
            and _v38_check_status(tampered, "audio_review_summary_hash") == "passed"
            and redaction.get("status") == "failed"
            and _v38_check_status(redaction, "redaction_scan") == "failed"
        )
        return ok, (
            f"release={release_id}, tracks=2, missing_gate={missing_gate_status}, synthetic_gate={synthetic_gate_status}, "
            f"sign={sign_status}, verify={verify.get('status')}, task={task.get('task_id')}, "
            f"tampered={_v38_check_status(tampered, 'audio_review_payload_hash')}, redaction={_v38_check_status(redaction, 'redaction_scan')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v52_arrangement_mix_controls_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v52-mix-controls-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        project_id = _v37_signed_project(server, "v5.2 Mix Controls")
        state_status, state = _release_http_json(server, "GET", f"/api/projects/{project_id}/versions/v001/mix-state")
        preview_status, preview = _release_http_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/mix-preview",
            {
                "label": "v5.2 lower melody and pan",
                "operations": [
                    {"op": "set_track_volume", "track_id": "track-001", "volume_db": -3},
                    {"op": "set_track_pan", "track_id": "track-001", "pan": 30},
                    {"op": "set_track_velocity_scale", "track_id": "track-002", "velocity_scale": 0.9},
                ],
            },
        )
        preview_id = str(preview.get("preview", {}).get("preview_id") or "")
        preview_midi_status, preview_midi = _release_http_bytes(server, "GET", f"/api/projects/{project_id}/versions/v001/mix-preview/{preview_id}/midi")
        apply_status, applied = _release_http_json(server, "POST", f"/api/projects/{project_id}/versions/v001/mix-preview/{preview_id}/apply", {"version_name": "v5.2 Mix Child"})
        child_version = str(applied.get("version", {}).get("version_id") or "")
        job_id = str(applied.get("job", {}).get("job_id") or "")
        child_job = _release_wait_http_job(server, job_id)
        stems_status, stems = _release_http_json(server, "POST", f"/api/projects/{project_id}/versions/{child_version}/mix-stems/render", {"require_wav": False, "force": True})
        final_status, _final = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": child_version})
        export_status, export = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stem_audio": False, "include_audio": True, "force": True})
        project_export_status, project_export = _release_http_json(server, "GET", f"/api/projects/{project_id}/export")
        final_dir = base / ".musicforge" / "projects" / project_id / "final-export"
        _v50_write_test_wav(final_dir / "song.wav", duration_seconds=30)
        audio_manifest = build_audio_artifact_manifest(
            artifact_id=f"project-{project_id}-{child_version}",
            scope="project_final_export",
            wav_path=final_dir / "song.wav",
            midi_path=final_dir / "song.mid",
            song_plan_path=final_dir / "song-plan.json",
            renderer_config=RendererConfig(soundfont_path="fixture.sf2"),
            extra_source={"project_id": project_id, "version_id": child_version, "source": "v5.2-release-check"},
        )
        write_audio_artifact_manifest(final_dir / "audio-artifact.json", audio_manifest)
        final_zip_status, _final_zip = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip", {"force": True})
        delivery_qa_status, _delivery_qa = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        delivery_reset_status, _delivery_reset = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "v5.2 audio fixture"})
        delivery_sign_status, _delivery_sign = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "release-check"})
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.2 Mix Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = str(release.get("release", {}).get("release_id") or "")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        review_status, review = _release_http_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-reviews",
            {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual v5.2 mix review.", "markers": [{"time_seconds": 2.0, "category": "mix_balance", "message": "melody low"}]},
        )
        review_id = str(review.get("review", {}).get("review_id") or "")
        patch_status, patch = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/{review_id}/markers/m-000001/mix-patch-draft", {})
        summary_status, summary = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews/refresh-summary")
        audio_refresh_status, audio_refresh = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        release_export_status, release_export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        missing_project = _v37_signed_project(server, "v5.2 Missing Mix Gate")
        _v50_add_project_audio(server, missing_project, duration_seconds=30)
        missing_release_status, missing_release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.2 Missing Mix Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        missing_release_id = str(missing_release.get("release", {}).get("release_id") or "")
        missing_track_status, _missing_track = _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/tracks", {"project_id": missing_project})
        missing_qa_status, _missing_qa = _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/qa/refresh")
        missing_mix_status, _missing_mix = _release_http_json(server, "POST", f"/api/releases/{missing_release_id}/signoff", {"signed_by": "release-check", "require_current_mix_state": True, "require_stem_audio_health": True})
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_current_mix_state": True, "require_stem_audio_health": True, "require_audio_health": True, "require_per_track_audio_review": True, "require_human_audio_review": True})
        zip_path = base / ".musicforge" / "releases" / release_id / "release-export.zip"
        verify = verify_release_zip(zip_path, require_audio=True, require_human_review=True, require_stems=True)

        def tamper_stem_health(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            payload["status"] = "passed" if payload.get("status") != "passed" else "failed"
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        stem_health_entry = next((item.get("path") for item in release_export.get("manifest", {}).get("files", []) if item.get("path", "").endswith("stems/stem-health.json")), "")
        tampered = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-stem-health.zip", transforms={stem_health_entry: tamper_stem_health}), require_audio=True, require_human_review=True, require_stems=True) if stem_health_entry else {"status": "missing"}
        midi_entry = next((item.get("path") for item in release_export.get("manifest", {}).get("files", []) if item.get("path", "").endswith("/song.mid")), "")
        tampered_mix = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-mix-source.zip", transforms={midi_entry: lambda data: data + b"\x00"}), require_audio=True, require_human_review=True, require_stems=True) if midi_entry else {"status": "missing"}
        plan_payload = json.loads((final_dir / "song-plan.json").read_text(encoding="utf-8"))
        plan_payload["title"] = f"{plan_payload.get('title', 'Song')} stale"
        (final_dir / "song-plan.json").write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        stale_release_status, stale_release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.2 Stale Mix Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        stale_release_id = str(stale_release.get("release", {}).get("release_id") or "")
        stale_track_status, _stale_track = _release_http_json(server, "POST", f"/api/releases/{stale_release_id}/tracks", {"project_id": project_id})
        stale_mix_status, stale_mix = _release_http_json(server, "POST", f"/api/releases/{stale_release_id}/signoff", {"signed_by": "release-check", "require_current_mix_state": True})
        stale_mix_reasons = []
        try:
            stale_mix_reasons = stale_mix.get("acceptance_gate", {}).get("audio", {}).get("mix", {}).get("tracks", [])[0].get("mix_state_stale_reasons", [])
        except Exception:
            stale_mix_reasons = []
        child_mix = next((item.get("mix", {}) for item in project_export.get("versions", []) if item.get("version_id") == child_version), {})
        ok = (
            state_status == 200
            and state.get("mix_state", {}).get("tracks")
            and preview_status == 201
            and preview_midi_status == 200
            and preview_midi.startswith(b"MThd")
            and apply_status == 201
            and child_job.get("status") == "completed"
            and stems_status == 200
            and stems.get("summary", {}).get("status") in {"passed", "warning"}
            and final_status == 200
            and export_status == 200
            and export.get("final_export", {}).get("mix", {}).get("mix_state_integrity_ok") is True
            and project_export_status == 200
            and child_mix.get("stem_health", {}).get("status") in {"passed", "warning"}
            and final_zip_status == 200
            and delivery_qa_status == 200
            and delivery_reset_status == 200
            and delivery_sign_status == 200
            and release_status == 201
            and track_status == 200
            and qa_status == 200
            and audio_status == 200
            and audio.get("summary", {}).get("status") == "passed"
            and review_status == 201
            and patch_status == 201
            and patch.get("patch", {}).get("source", {}).get("source_type") == "release_audio_review_marker"
            and summary_status == 200
            and summary.get("summary", {}).get("status") == "passed"
            and audio_refresh_status == 200
            and audio_refresh.get("summary", {}).get("status") == "passed"
            and release_export_status == 200
            and zip_status == 200
            and missing_release_status == 201
            and missing_track_status == 200
            and missing_qa_status == 200
            and missing_mix_status == 409
            and stale_release_status == 201
            and stale_track_status == 200
            and stale_mix_status == 409
            and "base_song_plan_hash" in stale_mix_reasons
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("audio", {}).get("mix", {}).get("status") == "passed"
            and verify.get("status") in {"passed", "warning"}
            and _v38_check_status(verify, "track_mix_state_current") == "passed"
            and _v38_check_status(verify, "track_stem_audio_health") == "passed"
            and tampered.get("status") == "failed"
            and _v38_check_status(tampered, "track_stem_audio_health") == "failed"
            and tampered_mix.get("status") == "failed"
            and _v38_check_status(tampered_mix, "track_mix_state_current") == "failed"
        )
        return ok, (
            f"preview={preview_status}, apply={apply_status}, stems={stems.get('summary', {}).get('status')}, "
            f"missing_mix_gate={missing_mix_status}, stale_mix_gate={stale_mix_status}/{stale_mix_reasons}, "
            f"sign={sign_status}, verify={verify.get('status')}, "
            f"tampered_stem={_v38_check_status(tampered, 'track_stem_audio_health')}, "
            f"tampered_mix={_v38_check_status(tampered_mix, 'track_mix_state_current')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v53_audio_revision_workbench_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v53-audio-revision-")).resolve()
    old_cwd = Path.cwd()
    server = None
    original_revision_render = None
    try:
        os.chdir(base)
        import song_agent.audio_revision as audio_revision_module
        from song_agent.server import create_server

        original_revision_render = audio_revision_module.render_audio

        def fake_revision_render(_midi_path: Path, wav_path: Path, _config: RendererConfig) -> Path:
            _v50_write_test_wav(Path(wav_path), duration_seconds=30)
            return Path(wav_path)

        audio_revision_module.render_audio = fake_revision_render
        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        project_id = _v37_signed_project(server, "v5.3 Audio Revision")
        _v50_add_project_audio(server, project_id, duration_seconds=30)
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.3 Audio Revision Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = str(release.get("release", {}).get("release_id") or "")
        track_status, _track = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        review_status, review = _release_http_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-reviews",
            {
                "track_id": "track-000001",
                "status": "needs_fix",
                "review_mode": "manual",
                "rating": 2,
                "playback_confirmed": True,
                "notes": "Drums overpower the hook.",
                "markers": [{"time_seconds": 2.0, "category": "mix_balance", "severity": "high", "message": "drums loud in hook"}],
            },
        )
        review_id = str(review.get("review", {}).get("review_id") or "")
        session_status, session = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {"title": "v5.3 smoke revision"})
        session_id = str(session.get("session", {}).get("session_id") or "")
        detail_status, detail = _release_http_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")
        issue = next((item for item in detail.get("issues", []) if item.get("source_review_id") == review_id), detail.get("issues", [{}])[0] if detail.get("issues") else {})
        issue_id = str(issue.get("issue_id") or "")
        unresolved_force_status, unresolved_force = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/close", {"force": True, "override_reason": "high issue must be rechecked first"})
        after_unresolved_force_status, after_unresolved_force = _release_http_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}")
        generate_status, generated = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/issues/{issue_id}/candidates/generate", {"max_candidates": 2})
        candidate_id = str((generated.get("candidates") or [{}])[0].get("candidate_id") or "")
        candidate_path = base / ".musicforge" / "releases" / release_id / "audio-revisions" / session_id / "candidates" / candidate_id / "candidate.json"
        original_candidate = read_json(candidate_path) if candidate_path.exists() else {}
        unsafe_candidate = json.loads(json.dumps(original_candidate))
        unsafe_candidate.setdefault("preview", {})["midi_path"] = "../outside.mid"
        unsafe_candidate["integrity_hash"] = _audio_revision_object_hash(unsafe_candidate, CANDIDATE_INTEGRITY_EXCLUDE)
        write_json(candidate_path, unsafe_candidate)
        unsafe_download_status, unsafe_download = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/midi")
        if original_candidate:
            write_json(candidate_path, original_candidate)
        midi_status, preview_midi = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/midi")
        candidate_review_status, candidate_review = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "A/B preview improves balance."})
        select_status, selected = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/select")
        apply_status, applied = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/candidates/{candidate_id}/apply", {"version_name": "v5.3 Audio Revision Applied"})
        applied_version = str(applied.get("applied_version_id") or "")
        old_review_status, old_review = _release_http_json(server, "GET", f"/api/releases/{release_id}/audio-reviews/{review_id}")
        recheck_status, recheck = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual recheck accepted after revision."})
        refresh_status, refreshed = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/refresh")
        close_status, closeout = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{session_id}/close")
        marker_guard_review_status, marker_guard_review = _release_http_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-reviews",
            {
                "track_id": "track-000001",
                "status": "needs_fix",
                "review_mode": "manual",
                "rating": 2,
                "playback_confirmed": True,
                "notes": "New high-priority marker after closeout.",
                "markers": [{"time_seconds": 4.0, "category": "mix_balance", "severity": "high", "message": "new balance issue after closeout"}],
            },
        )
        marker_gate_status, marker_gate = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_revision_closeout": True})
        marker_session_status, marker_session = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions", {"title": "v5.3 marker coverage"})
        marker_session_id = str(marker_session.get("session", {}).get("session_id") or "")
        marker_review_id = str(marker_guard_review.get("review", {}).get("review_id") or "")
        marker_detail_status, marker_detail = _release_http_json(server, "GET", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}")
        marker_issue = next((item for item in marker_detail.get("issues", []) if item.get("source_review_id") == marker_review_id), marker_detail.get("issues", [{}])[0] if marker_detail.get("issues") else {})
        marker_issue_id = str(marker_issue.get("issue_id") or "")
        marker_generate_status, marker_generated = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/issues/{marker_issue_id}/candidates/generate", {"max_candidates": 1})
        marker_candidate_id = str((marker_generated.get("candidates") or [{}])[0].get("candidate_id") or "")
        marker_candidate_review_status, _marker_candidate_review = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/candidates/{marker_candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 4, "playback_confirmed": True, "notes": "Second A/B preview is acceptable."})
        marker_select_status, _marker_select = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/candidates/{marker_candidate_id}/select")
        marker_apply_status, marker_applied = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/candidates/{marker_candidate_id}/apply", {"version_name": "v5.3 Marker Coverage Applied"})
        marker_applied_version = str(marker_applied.get("applied_version_id") or "")
        marker_recheck_status, marker_recheck = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-reviews", {"track_id": "track-000001", "status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual recheck accepted after marker guard revision."})
        marker_refresh_status, marker_refreshed = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/refresh")
        marker_close_status, marker_closeout = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-revisions/{marker_session_id}/close")
        delivery_reset_status, _delivery_reset = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": "v5.3 audio revision applied"})
        delivery_sign_status, _delivery_sign = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "release-check"})
        qa_refresh_status, _qa_refresh = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_refresh_status, audio_refresh = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_audio_health": True, "require_per_track_audio_review": True, "require_audio_revision_closeout": True})
        zip_path = base / ".musicforge" / "releases" / release_id / "release-export.zip"
        verify = verify_release_zip(zip_path, require_audio=True, require_human_review=True, require_audio_revisions=True)
        candidate_entry = next((item.get("path") for item in export.get("manifest", {}).get("audio_revisions", {}).get("files", []) if str(item.get("path") or "").startswith("audio-revisions/selected-candidates/")), "")

        def tamper_candidate(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            payload["applied_version_id"] = "v999"
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        tampered = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-audio-revision.zip", transforms={candidate_entry: tamper_candidate}), require_audio=True, require_human_review=True, require_audio_revisions=True) if candidate_entry else {"status": "missing"}
        ok = (
            release_status == 201
            and track_status == 200
            and qa_status == 200
            and audio_status == 200
            and audio.get("summary", {}).get("status") == "passed"
            and review_status == 201
            and session_status == 201
            and detail_status == 200
            and issue.get("severity") == "high"
            and unresolved_force_status == 409
            and "high_issue_unresolved" in " ".join(after_unresolved_force.get("closeout", {}).get("force_blockers", []))
            and after_unresolved_force.get("session", {}).get("status") != "closed"
            and generate_status == 201
            and unsafe_download_status == 409
            and b"error" in unsafe_download
            and midi_status == 200
            and preview_midi.startswith(b"MThd")
            and candidate_review_status == 200
            and candidate_review.get("candidate", {}).get("review", {}).get("status") == "accepted"
            and select_status == 200
            and selected.get("candidate", {}).get("selected") is True
            and apply_status == 200
            and applied_version
            and old_review_status == 200
            and old_review.get("review", {}).get("stale") is True
            and recheck_status == 201
            and recheck.get("review", {}).get("version_id") == applied_version
            and recheck.get("review", {}).get("stale") is False
            and refresh_status == 200
            and refreshed.get("rechecked_count") == 1
            and close_status == 200
            and closeout.get("closeout", {}).get("status") == "passed"
            and marker_guard_review_status == 201
            and marker_gate_status == 409
            and "Audio revision closeout gate failed" in str(marker_gate.get("error") or "")
            and marker_session_status == 201
            and marker_detail_status == 200
            and marker_generate_status == 201
            and marker_candidate_review_status == 200
            and marker_select_status == 200
            and marker_apply_status == 200
            and marker_applied_version
            and marker_recheck_status == 201
            and marker_recheck.get("review", {}).get("version_id") == marker_applied_version
            and marker_refresh_status == 200
            and marker_refreshed.get("rechecked_count") == 1
            and marker_close_status == 200
            and marker_closeout.get("closeout", {}).get("status") == "passed"
            and delivery_reset_status == 200
            and delivery_sign_status == 200
            and qa_refresh_status == 200
            and audio_refresh_status == 200
            and audio_refresh.get("summary", {}).get("status") == "passed"
            and export_status == 200
            and export.get("manifest", {}).get("audio_revisions", {}).get("status") == "passed"
            and zip_status == 200
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("audio", {}).get("audio_revision", {}).get("status") == "passed"
            and verify.get("status") in {"passed", "warning"}
            and _v38_check_status(verify, "audio_revision_evidence") == "passed"
            and tampered.get("status") == "failed"
            and _v38_check_status(tampered, "audio_revision_evidence") == "failed"
        )
        return ok, (
            f"session={session_status}, generate={generate_status}, apply={apply_status}, close={close_status}, "
            f"force_unresolved={unresolved_force_status}, path_pollution={unsafe_download_status}, marker_gate={marker_gate_status}, sign={sign_status}, verify={verify.get('status')}, "
            f"revision_verify={_v38_check_status(verify, 'audio_revision_evidence')}, "
            f"candidate_tamper={_v38_check_status(tampered, 'audio_revision_evidence')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if original_revision_render is not None:
            audio_revision_module.render_audio = original_revision_render
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v54_mastering_qa_smoke(root: Path) -> tuple[bool, str]:
    base = Path(tempfile.mkdtemp(prefix="mf-v54-mastering-")).resolve()
    old_cwd = Path.cwd()
    server = None
    try:
        os.chdir(base)
        from song_agent.server import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        first_project = _v37_signed_project(server, "v5.4 Mastering One")
        second_project = _v37_signed_project(server, "v5.4 Mastering Two")
        _v50_add_project_audio(server, first_project, duration_seconds=30)
        _v50_add_project_audio(server, second_project, duration_seconds=30)
        release_status, release = _release_http_json(server, "POST", "/api/releases", {"name": "v5.4 Mastering Release", "release_type": "ep", "primary_artist": "MusicForge"})
        release_id = str(release.get("release", {}).get("release_id") or "")
        first_track_status, _first = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        second_track_status, _second = _release_http_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        qa_status, _qa = _release_http_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        audio_status, audio = _release_http_json(server, "POST", f"/api/releases/{release_id}/audio-qa", {"require_audio": True})
        missing_mastering_status, _missing_mastering = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_mastering_qa": True})
        profile_status, profiles = _release_http_json(server, "GET", "/api/mastering/profiles")
        analyze_status, analyze = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        plan_status, plan = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/plan", {})
        candidate_status, candidate = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates", {})
        candidate_id = str(candidate.get("candidate", {}).get("candidate_id") or "")
        review_status, review = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/review", {"status": "accepted", "review_mode": "manual", "rating": 5, "playback_confirmed": True, "notes": "Manual A/B mastering accepted."})
        select_status, selected = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/select", {})
        audio_download_status, audio_bytes = _release_http_bytes(server, "GET", f"/api/releases/{release_id}/mastering/candidates/{candidate_id}/tracks/track-000001/audio")
        export_status, export = _release_http_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = _release_http_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signoff = _release_http_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-check", "require_mastering_qa": True})
        signed_mutation_status, _signed_mutation = _release_http_json(server, "POST", f"/api/releases/{release_id}/mastering/analyze", {"profile_id": "demo_review"})
        zip_path = base / ".musicforge" / "releases" / release_id / "release-export.zip"
        verify = verify_release_zip(zip_path, require_audio=True, require_mastering=True)
        with zipfile.ZipFile(zip_path, "r") as archive:
            track_wav = next(name for name in archive.namelist() if name.startswith("tracks/") and name.endswith("/song.wav"))
            selected_path = "mastering/selected-candidate.json"

        def tamper_track_wav(_data: bytes) -> bytes:
            return b"not-a-real-wav"

        def tamper_selected(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            payload.setdefault("review", {})["reviewed_by"] = "tampered-reviewer"
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        tampered_wav = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-mastering-wav.zip", transforms={track_wav: tamper_track_wav}), require_audio=True, require_mastering=True)
        tampered_selected = verify_release_zip(_v38_rewrite_zip(zip_path, base / "tampered-mastering-selected.zip", transforms={selected_path: tamper_selected}), require_audio=True, require_mastering=True)
        ok = (
            release_status == 201
            and first_track_status == 200
            and second_track_status == 200
            and qa_status == 200
            and audio_status == 200
            and audio.get("summary", {}).get("status") == "passed"
            and missing_mastering_status == 409
            and profile_status == 200
            and any(item.get("profile_id") == "demo_review" for item in profiles.get("profiles", []))
            and analyze_status == 200
            and analyze.get("summary", {}).get("status") in {"passed", "warning"}
            and plan_status == 200
            and plan.get("plan", {}).get("summary", {}).get("track_count") == 2
            and candidate_status == 201
            and review_status == 200
            and review.get("candidate", {}).get("review", {}).get("status") == "accepted"
            and select_status == 200
            and selected.get("candidate", {}).get("selected") is True
            and audio_download_status == 200
            and audio_bytes.startswith(b"RIFF")
            and export_status == 200
            and export.get("manifest", {}).get("mastering", {}).get("selected_candidate_id") == candidate_id
            and zip_status == 200
            and sign_status == 200
            and signoff.get("signoff", {}).get("acceptance_gate", {}).get("mastering", {}).get("status") == "passed"
            and signed_mutation_status == 409
            and verify.get("status") in {"passed", "warning"}
            and _v38_check_status(verify, "mastering_evidence") == "passed"
            and tampered_wav.get("status") == "failed"
            and _v38_check_status(tampered_wav, "mastering_evidence") == "failed"
            and tampered_selected.get("status") == "failed"
            and _v38_check_status(tampered_selected, "mastering_evidence") == "failed"
        )
        return ok, (
            f"missing={missing_mastering_status}, analyze={analyze_status}/{analyze.get('summary', {}).get('status')}, "
            f"candidate={candidate_status}, select={select_status}, sign={sign_status}, verify={verify.get('status')}, "
            f"signed_mutation={signed_mutation_status}, tamper_wav={_v38_check_status(tampered_wav, 'mastering_evidence')}, "
            f"tamper_selected={_v38_check_status(tampered_selected, 'mastering_evidence')}"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(old_cwd)
        if base.exists():
            shutil.rmtree(base)


def _v37_signed_project(server: Any, title: str) -> str:
    created_status, created = _release_http_json(server, "POST", "/api/projects", {"name": title})
    if created_status != 201:
        raise RuntimeError(f"create project failed: {created_status} {created}")
    project_id = created["project"]["project_id"]
    version_status, version = _release_http_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions",
        {"name": title, "request": {"title": title, "language": "English", "style": "synth pop", "theme": "release workspace", "tempo_bpm": 120, "key": "C"}},
    )
    if version_status != 202:
        raise RuntimeError(f"create version failed: {version_status} {version}")
    job = _release_wait_http_job(server, version["job"]["job_id"])
    if job.get("status") != "completed":
        raise RuntimeError(f"job failed: {job}")
    final_status, _final = _release_http_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
    export_status, _exported = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
    zip_status, _zipped = _release_http_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
    qa_status, qa = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
    sign_status, signoff = _release_http_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "release-check"})
    if not (final_status == 200 and export_status == 200 and zip_status == 200 and qa_status == 200 and sign_status == 200 and qa.get("summary", {}).get("handoff_allowed") is True and signoff.get("summary", {}).get("status") == "signed"):
        raise RuntimeError(f"project signoff chain failed: final={final_status} export={export_status} zip={zip_status} qa={qa_status} sign={sign_status}")
    return project_id


def _release_http_json(server: Any, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    status, body = _release_http_request(server, method, path, payload=payload)
    if isinstance(body, dict):
        return status, body
    return status, {}


def _release_http_bytes(server: Any, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, bytes]:
    status, body = _release_http_request(server, method, path, payload=payload)
    if isinstance(body, bytes):
        return status, body
    return status, json.dumps(body, sort_keys=True).encode("utf-8")


def _release_http_request(server: Any, method: str, path: str, *, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | bytes]:
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=15)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    content_type = response.getheader("Content-Type", "")
    connection.close()
    if content_type.startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data


def _release_item_id(queue: dict[str, Any], action: str, *, required: bool = True) -> str:
    for item in queue.get("items", []):
        if isinstance(item, dict) and item.get("action") == action:
            return str(item.get("item_id") or "")
    if required:
        raise KeyError(f"missing action queue item: {action}")
    return ""


def _release_item(queue: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in queue.get("items", []):
        if isinstance(item, dict) and item.get("item_id") == item_id:
            return item
    return {}


def _release_wait_http_job(server: Any, job_id: str) -> dict[str, Any]:
    for _ in range(160):
        status, job = _release_http_json(server, "GET", f"/api/jobs/{job_id}")
        if status == 200 and job.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise TimeoutError(f"Job {job_id} did not finish.")


def _tiny_wav_bytes() -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes((1200).to_bytes(2, "little", signed=True) * 512)
    return buffer.getvalue()


def _tiny_reference_midi_bytes() -> bytes:
    meta = _midi_track([(0, b"\xff\x51\x03\x07\xa1\x20")])
    melody = _midi_track([(0, b"\x90\x40\x64"), (480, b"\x40\x00"), (0, b"\x43\x64"), (480, b"\x43\x00")])
    bass = _midi_track([(0, b"\x92\x24\x58"), (960, b"\x82\x24\x00")])
    return b"MThd" + struct.pack(">IHHH", 6, 1, 3, 480) + meta + melody + bass


def _midi_track(events: list[tuple[int, bytes]]) -> bytes:
    body = bytearray()
    for delta, payload in events:
        body.extend(_midi_vlq(delta))
        body.extend(payload)
    body.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _midi_vlq(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
        value >>= 7
    out = bytearray()
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            return bytes(out)


class _SmokeProject:
    project_id = "release-smoke"
    name = "Release Smoke"


class _SmokeVersion:
    version_id = "v001"
    name = "Release Smoke"
    job_id = "release-smoke"
    note = ""

    def __init__(self, run_dir: Path) -> None:
        self.output_dir = str(run_dir)


class _SmokeJob:
    def __init__(self, job_id: str, run_dir: Path, request: dict[str, object]) -> None:
        now = "2026-05-06T00:00:00+00:00"
        self.job_id = job_id
        self.title = str(request.get("title") or job_id)
        self.output_dir = str(run_dir)
        self.status = "completed"
        self.created_at = now
        self.updated_at = now
        self.input_payload = dict(request)
        self.generation_mode = "local"
        self.pipeline_mode = "single"
        self.summary = {"title": self.title}
        self.artifacts = {"midi": str(run_dir / "renders" / "song.mid")}


def _skip_file(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_allowed_fixture_hit(relative: str, line: str) -> bool:
    normalized = relative.replace("\\", "/")
    if normalized.startswith("material/"):
        return True
    if normalized.startswith("tests/"):
        return True
    if normalized == "song_agent/release_checks.py":
        return True
    if normalized in {"README.md", "CHANGELOG.md"} and (
        "Authorization: Bearer" in line or "access token" in line.lower()
    ):
        return True
    return False


def _redact_line(line: str) -> str:
    line = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_***", line)
    line = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_***", line)
    line = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", line)
    line = re.sub(r"(Authorization:\s*Bearer\s+)\S+", r"\1***", line, flags=re.IGNORECASE)
    line = re.sub(r"(api_key\s*[:=]\s*['\"])[^'\"]+", r"\1***", line, flags=re.IGNORECASE)
    line = re.sub(r"(access_token\s*[:=]\s*['\"])[^'\"]+", r"\1***", line, flags=re.IGNORECASE)
    return line


def _last_lines(value: str, max_lines: int = 8) -> str:
    lines = [line for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])
