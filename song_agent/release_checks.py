from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import hashlib
import base64
import struct
import threading
import time
import wave
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
