from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from song_agent import __version__


SECRET_PATTERNS = tuple(
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
)
SECRET_SCAN_PATHS = (
    "README.md",
    "CHANGELOG.md",
    ".github",
    "docs",
    "material",
    "song_agent",
    "tests",
    "tools",
    "pyproject.toml",
    ".gitignore",
)


def git_status_check(root: Path) -> tuple[bool, str]:
    status = _run(["git", "status", "--short", "--branch"], root)
    status_text = status.stdout.strip()
    return status.returncode == 0 and _status_is_clean(status_text), status_text


def remote_url_token_check(root: Path) -> tuple[bool, str]:
    remotes = _run(["git", "remote", "-v"], root)
    return remotes.returncode == 0 and not _remote_has_token(remotes.stdout), _redact_remote(remotes.stdout.strip())


def musicforge_configs_untracked_check(root: Path) -> tuple[bool, str]:
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
    return tracked.returncode == 0 and not tracked.stdout.strip(), tracked.stdout.strip()


def musicforge_configs_ignored_check(root: Path) -> tuple[bool, str]:
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
    return ignored.returncode == 0, ignored.stdout.strip()


def version_consistency(root: Path) -> tuple[bool, str]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    pyproject_version = match.group(1) if match else ""
    ok = pyproject_version == __version__ and f"## v{__version__}" in changelog
    return ok, f"package={__version__}, pyproject={pyproject_version}"


def secret_scan(root: Path) -> tuple[bool, str]:
    matches: list[str] = []
    for scan_path in SECRET_SCAN_PATHS:
        path = root / scan_path
        files = [file for file in path.rglob("*") if file.is_file()] if path.is_dir() else [path] if path.exists() else []
        for file in files:
            if _skip_file(file):
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = file.relative_to(root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in SECRET_PATTERNS) and not _is_allowed_fixture_hit(relative):
                    matches.append(f"{relative}:{line_number}: {_redact_line(line.strip())}")
    return (False, "\n".join(matches[:20])) if matches else (True, "no disallowed secret patterns found")


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, shell=False, encoding="utf-8", errors="replace")


def _status_is_clean(status_text: str) -> bool:
    lines = [line for line in status_text.splitlines() if line.strip()]
    return not lines or (
        len(lines) == 1
        and lines[0].startswith("## ")
        and "[ahead" not in lines[0]
        and "[behind" not in lines[0]
    )


def _remote_has_token(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("x-access-token", "ghp_", "github_pat_"))


def _redact_remote(value: str) -> str:
    value = re.sub(r"https://[^@\s]+@", "https://***@", value)
    return re.sub(r"(x-access-token:)[^@\s]+", r"\1***", value, flags=re.IGNORECASE)


def _skip_file(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in path.parts)


def _is_allowed_fixture_hit(relative: str) -> bool:
    return relative.startswith(("material/", "tests/")) or relative.endswith(
        ("release_check/checks/legacy/monolith.py", "release_check/repository_checks.py")
    )


def _redact_line(line: str) -> str:
    line = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_***", line)
    line = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_***", line)
    line = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", line)
    line = re.sub(r"(Authorization:\s*Bearer\s+)\S+", r"\1***", line, flags=re.IGNORECASE)
    line = re.sub(r"(api_key\s*[:=]\s*['\"])[^'\"]+", r"\1***", line, flags=re.IGNORECASE)
    return re.sub(r"(access_token\s*[:=]\s*['\"])[^'\"]+", r"\1***", line, flags=re.IGNORECASE)
