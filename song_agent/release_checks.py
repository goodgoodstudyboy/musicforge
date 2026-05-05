from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from song_agent import __version__


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
    tracked = _run(["git", "ls-files", ".musicforge/provider.json", ".musicforge/renderer.json"], root)
    report.add(
        ".musicforge configs untracked",
        tracked.returncode == 0 and not tracked.stdout.strip(),
        tracked.stdout.strip(),
    )
    ignored = _run(["git", "check-ignore", "-v", ".musicforge/provider.json", ".musicforge/renderer.json"], root)
    report.add(
        ".musicforge configs ignored",
        ignored.returncode == 0,
        ignored.stdout.strip(),
    )
    report.add("version consistency", *_version_consistency(root))
    report.add("secret scan", *_secret_scan(root))
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


def _skip_file(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)


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
