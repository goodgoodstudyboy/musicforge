from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from song_agent import __version__
from song_agent.agent.pipeline import deterministic_compose
from song_agent.edits import EditIntent, apply_edit_intent, build_edit_metadata
from song_agent.edit_presets import EditPresetStore, merge_preset_intent
from song_agent.final_export import FinalExportOptions, build_final_export_bundle, build_final_export_zip
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.project_compare import compare_project_versions
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projectio import write_json
from song_agent.projects import ProjectStore
from song_agent.provider import ProviderConfig
from song_agent.provider_edits import generate_provider_edit_patch, apply_provider_edit_patch
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongRequest


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
    return subprocess.run(
        command,
        cwd=cwd,
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
                    "total_tokens": 0,
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
            compare = compare_project_versions(document, "v001", "v002")
            serialized = str(compare) + str(snapshot)
            ok = (
                compare["right"]["edit"]["provider_mode"] == "provider"
                and compare["right"]["edit"]["provider_patch"]["operation_count"] >= 1
                and "sk-release-secret" not in serialized
            )
            return ok, f"template={template.template_id}, operations={len(patch.operations)}, compare={compare['summary']['recommendation']}"
    except Exception as exc:
        return False, str(exc)


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
