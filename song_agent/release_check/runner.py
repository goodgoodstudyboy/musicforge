from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from song_agent import __version__
from song_agent.architecture_guardrails import update_architecture_release_metrics
from song_agent.release_check.matrix import ReleaseCheckDefinition, ReleaseCheckMatrixError, definition_to_dict, select_check_definitions
from song_agent.release_check.performance import check_budget_status, performance_summary


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    check_id: str = ""
    group: str = ""
    version: str | None = None
    kind: str = ""
    risk: str = ""
    status: str = "passed"
    duration_ms: int = 0
    stdout_tail: str = ""
    stderr_tail: str = ""
    warnings: list[str] = field(default_factory=list)
    expected_warning_matches: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_budget_seconds: float | None = None
    duration_budget_status: str = "not_configured"
    budget_warning_only: bool = True


@dataclass
class ReleaseCheckReport:
    results: list[CheckResult] = field(default_factory=list)
    profile: str = "full"
    groups: list[str] = field(default_factory=list)
    since: str | None = None
    only: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    environment: ImplementationDocument = field(default_factory=dict)
    selected_checks: list[ImplementationDocument] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(result.ok for result in self.results)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        status = "passed" if ok else "failed"
        self.results.append(CheckResult(name=name, ok=ok, detail=detail, status=status))

    def to_json_report(self) -> DomainDocument:
        failures = [result for result in self.results if not result.ok]
        warning_results = [result for result in self.results if result.status == "warning"]
        checks_with_warnings = [
            result
            for result in self.results
            if result.warnings
            or result.expected_warning_matches
            or result.status == "warning"
            or result.duration_budget_status == "warning"
        ]
        expected_warning_count = sum(len(result.expected_warning_matches) for result in self.results)
        raw_warning_count = sum(len(result.warnings) for result in self.results)
        unexpected_warning_count = max(0, raw_warning_count - expected_warning_count)
        timed_out = [result for result in self.results if result.status == "timed_out"]
        network = [result for result in self.results if result.status == "network_error"]
        slowest = sorted(self.results, key=lambda result: result.duration_ms, reverse=True)[:10]
        performance = performance_summary(self.results, profile=self.profile, duration_ms=self.duration_ms)
        return sanitize_report(
            {
                "schema_version": 1,
                "app_version": __version__,
                "profile": self.profile,
                "groups": self.groups,
                "since": self.since,
                "only": self.only,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration_ms": self.duration_ms,
                "ok": self.ok,
                "summary": {
                    "total": len(self.results),
                    "passed": sum(1 for result in self.results if result.status == "passed"),
                    "failed": len(failures),
                    "warning": len(warning_results),
                    "checks_with_warnings": len(checks_with_warnings),
                    "expected_warnings": expected_warning_count,
                    "unexpected_warnings": unexpected_warning_count,
                    "timed_out": len(timed_out),
                    "network_error": len(network),
                    "skipped": sum(1 for result in self.results if result.status == "skipped"),
                    "slowest": [{"check_id": result.check_id, "duration_ms": result.duration_ms} for result in slowest],
                    "slow_checks": performance["slow_checks"],
                    "checks_over_budget": performance["checks_over_budget"],
                    "duration_budget_status": performance["duration_budget_status"],
                    "profile_duration_budget_seconds": performance["profile_duration_budget_seconds"],
                },
                "performance": performance,
                "environment": self.environment,
                "selected_checks": self.selected_checks,
                "results": [result_to_dict(result) for result in self.results],
            }
        )

    def to_timing_report(self) -> DomainDocument:
        slowest = sorted(self.results, key=lambda result: result.duration_ms, reverse=True)[:20]
        performance = performance_summary(self.results, profile=self.profile, duration_ms=self.duration_ms)
        return sanitize_report(
            {
                "schema_version": 1,
                "profile": self.profile,
                "duration_ms": self.duration_ms,
                "slowest": [{"check_id": result.check_id, "name": result.name, "duration_ms": result.duration_ms, "status": result.status} for result in slowest],
                "slow_checks": performance["slow_checks"],
                "checks_over_budget": performance["checks_over_budget"],
                "duration_budget_status": performance["duration_budget_status"],
                "profile_duration_budget_seconds": performance["profile_duration_budget_seconds"],
                "performance": performance,
                "results": [
                    {
                        "check_id": result.check_id,
                        "name": result.name,
                        "status": result.status,
                        "duration_ms": result.duration_ms,
                        "duration_budget_seconds": result.duration_budget_seconds,
                        "duration_budget_status": result.duration_budget_status,
                    }
                    for result in self.results
                ],
            }
        )


def result_to_dict(result: CheckResult) -> DomainDocument:
    return {
        "check_id": result.check_id,
        "name": result.name,
        "group": result.group,
        "version": result.version,
        "kind": result.kind,
        "risk": result.risk,
        "status": result.status,
        "ok": result.ok,
        "duration_ms": result.duration_ms,
        "detail": result.detail,
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "warnings": result.warnings,
        "expected_warning_matches": result.expected_warning_matches,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_budget_seconds": result.duration_budget_seconds,
        "duration_budget_status": result.duration_budget_status,
        "budget_warning_only": result.budget_warning_only,
    }


def run_release_check_matrix(
    *,
    repo_root: Path | None = None,
    profile: str = "full",
    groups: list[str] | None = None,
    since: str | None = None,
    only: list[str] | None = None,
    run_tests: bool = True,
    fail_fast: bool = False,
    timeout_seconds: int | None = None,
    progress: Callable[[ReleaseCheckDefinition], None] | None = None,
    definitions: list[ReleaseCheckDefinition] | None = None,
) -> ReleaseCheckReport:
    root = repo_root or Path.cwd()
    started = _now()
    start = time.perf_counter()
    selected = select_check_definitions(profile=profile, groups=groups, since=since, only=only, run_tests=run_tests, definitions=definitions)
    report = ReleaseCheckReport(
        profile=profile,
        groups=list(groups or []),
        since=since,
        only=list(only or []),
        started_at=started,
        environment=_environment(root),
        selected_checks=[definition_to_dict(definition) for definition in selected],
    )
    if not selected:
        report.results.append(_empty_selection_result(profile=profile, groups=groups, since=since, only=only))
        report.finished_at = _now()
        report.duration_ms = int((time.perf_counter() - start) * 1000)
        return report
    for definition in selected:
        if progress is not None:
            progress(definition)
        result = _run_definition(definition, root, profile=profile, timeout_seconds=timeout_seconds)
        report.results.append(result)
        if fail_fast and not result.ok:
            break
    report.finished_at = _now()
    report.duration_ms = int((time.perf_counter() - start) * 1000)
    profile_budget_result = _profile_budget_result(report)
    if profile_budget_result is not None:
        report.results.append(profile_budget_result)
    if any(definition.check_id == "v1214.architecture_guardrails_smoke" for definition in selected):
        update_architecture_release_metrics(
            root / "runs" / "architecture" / "metrics.json",
            profile=profile,
            duration_ms=report.duration_ms,
            status="passed" if report.ok else "failed",
            check_count=len(report.results),
        )
    return report


def _profile_budget_result(report: ReleaseCheckReport) -> CheckResult | None:
    performance = performance_summary(report.results, profile=report.profile, duration_ms=report.duration_ms)
    if performance.get("duration_budget_status") != "failed" or not performance.get("profile_over_budget"):
        return None
    budget = performance.get("profile_duration_budget_seconds")
    now = _now()
    return CheckResult(
        name="release-check profile duration budget",
        ok=False,
        detail=f"profile duration budget exceeded: {report.duration_ms}ms > {budget}s",
        check_id="release_check.profile_duration_budget",
        group="release-check",
        kind="performance",
        risk="high",
        status="failed",
        started_at=now,
        finished_at=now,
        duration_budget_seconds=float(budget) if budget is not None else None,
        duration_budget_status="failed",
        budget_warning_only=False,
    )


def _empty_selection_result(*, profile: str, groups: list[str] | None, since: str | None, only: list[str] | None) -> CheckResult:
    filters = []
    if groups:
        filters.append(f"groups={','.join(groups)}")
    if since:
        filters.append(f"since={since}")
    if only:
        filters.append(f"only={','.join(only)}")
    suffix = f" ({'; '.join(filters)})" if filters else ""
    now = _now()
    return CheckResult(
        name="release-check selection",
        ok=False,
        detail=f"No release-checks selected for profile={profile}{suffix}. Adjust --profile, --group, --since, or --only.",
        check_id="release_check.selection",
        group="meta",
        kind="selection",
        risk="critical",
        status="failed",
        started_at=now,
        finished_at=now,
    )


def write_json_report(report: ReleaseCheckReport, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_json_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def write_timing_report(report: ReleaseCheckReport, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_timing_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def print_release_check_report(report: ReleaseCheckReport) -> None:
    print("MusicForge release-check")
    for result in report.results:
        print(f"{result.name}: {_display_status(result)} ({result.duration_ms} ms)")
        if result.detail:
            for line in result.detail.splitlines():
                print(f"  {line}")
    print(f"summary: {'ok' if report.ok else 'failed'} ({report.duration_ms} ms)")


def sanitize_report(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_report(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_report(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _run_definition(
    definition: ReleaseCheckDefinition,
    root: Path,
    *,
    profile: str,
    timeout_seconds: int | None = None,
) -> CheckResult:
    started_at = _now()
    start = time.perf_counter()
    timeout = _effective_timeout(definition.timeout_seconds, timeout_seconds)
    try:
        if definition.command:
            result = _run_command(list(definition.command), root, timeout_seconds=timeout)
        elif definition.callable_name:
            result = _run_callable(definition.callable_name, root)
        else:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} has no executable target.")
    except Exception as exc:
        status = "network_error" if definition.kind == "remote" and _looks_like_network_error(str(exc)) else "failed"
        result = CheckResult(name=definition.name, ok=False, status=status, detail=str(exc))
    result.check_id = definition.check_id
    result.name = definition.name
    result.group = definition.group
    result.version = definition.version
    result.kind = definition.kind
    result.risk = definition.risk
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    result.duration_budget_seconds = definition.duration_budget_seconds
    result.budget_warning_only = definition.budget_warning_only
    result.duration_budget_status = check_budget_status(
        duration_ms=result.duration_ms,
        duration_budget_seconds=definition.duration_budget_seconds,
        profile=profile,
        budget_enforced_profiles=definition.budget_enforced_profiles,
        budget_warning_only=definition.budget_warning_only,
    )
    if result.duration_budget_status == "failed":
        result.ok = False
        result.status = "failed"
        budget_detail = f"duration budget exceeded: {result.duration_ms}ms > {definition.duration_budget_seconds}s"
        result.detail = f"{result.detail}\n{budget_detail}" if result.detail else budget_detail
    result.started_at = started_at
    result.finished_at = _now()
    output_for_expected = "\n".join([result.detail, result.stdout_tail, result.stderr_tail, *result.warnings])
    expected = [pattern for pattern in definition.expected_warnings if pattern and pattern in output_for_expected]
    result.expected_warning_matches = expected
    result.detail = _redact_text(result.detail)
    result.stdout_tail = _redact_text(result.stdout_tail)
    result.stderr_tail = _redact_text(result.stderr_tail)
    result.warnings = [_redact_text(warning) for warning in result.warnings]
    result.expected_warning_matches = [_redact_text(warning) for warning in result.expected_warning_matches]
    return result


def _run_command(command: list[str], root: Path, *, timeout_seconds: int) -> CheckResult:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_output(exc.stdout)
        stderr = _coerce_output(exc.stderr)
        return CheckResult(
            name=" ".join(command),
            ok=False,
            status="timed_out",
            detail=f"timed out after {timeout_seconds}s",
            stdout_tail=_last_lines(stdout),
            stderr_tail=_last_lines(stderr),
            warnings=_warning_lines(stdout + "\n" + stderr),
        )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return CheckResult(
        name=" ".join(command),
        ok=completed.returncode == 0,
        status="passed" if completed.returncode == 0 else "failed",
        detail=_last_lines(output),
        stdout_tail=_last_lines(completed.stdout or ""),
        stderr_tail=_last_lines(completed.stderr or ""),
        warnings=_warning_lines(output),
    )


def _run_callable(callable_name: str, root: Path) -> CheckResult:
    from song_agent.release_check.checks.registry import resolve_callable

    target = resolve_callable(callable_name)
    ok, detail = target(root)
    return CheckResult(name=callable_name, ok=bool(ok), status="passed" if ok else "failed", detail=str(detail or ""))


def _effective_timeout(default: int, override: int | None) -> int:
    if override is None:
        return max(1, int(default or 10))
    return max(10, int(override))


def _environment(root: Path) -> ImplementationDocument:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repo_root": ".",
        "git_head": _quick_git(root, ["rev-parse", "HEAD"]),
        "git_branch_status": _quick_git(root, ["status", "--short", "--branch"]),
    }


def _quick_git(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, shell=False, timeout=10, encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return _redact_text((completed.stdout or completed.stderr or "").strip())


def _display_status(result: CheckResult) -> str:
    if result.ok:
        return "ok"
    return result.status or "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _last_lines(value: str, max_lines: int = 8) -> str:
    lines = [line for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _warning_lines(value: str) -> list[str]:
    return [line for line in value.splitlines() if "warning" in line.lower()][:20]


def _looks_like_network_error(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("timed out", "could not resolve", "failed to connect", "connection reset", "network"))


def _redact_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"https://[^@\s]+@", "https://***@", text)
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_***", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_***", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", text)
    text = re.sub(r"(Authorization:\s*Bearer\s+)\S+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(r"(api_key\s*[:=]\s*['\"])[^'\"]+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(r"(access_token\s*[:=]\s*['\"])[^'\"]+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(
        r"C:\\Users\\[^\\\r\n]+\\Documents\\projects\\githubkey\.txt",
        lambda _match: "[redacted local token path]",
        text,
        flags=re.IGNORECASE,
    )
    return text
