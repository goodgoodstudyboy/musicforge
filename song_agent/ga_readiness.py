from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomllib

from song_agent import __version__
from song_agent.audio_profiles import AudioProfileStore, AudioProfileNotFoundError
from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package
from song_agent.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.music_acceptance import AcceptanceStore, acceptance_report_summary, stable_hash
from song_agent.projectio import read_json, write_json
from song_agent.provider import ProviderError, load_provider_config, provider_configured
from song_agent.release_check_runner import run_release_check_matrix


GA_READINESS_PACKAGE_TYPE = "musicforge_ga_readiness_report"
GA_READINESS_SCHEMA_VERSION = 1
DEFAULT_GA_REPORT_PATH = Path("runs") / "ga-readiness" / "ga-readiness-report.json"

REQUIRED_DOCS = (
    "docs/GETTING_STARTED.md",
    "docs/LOCAL_ACCEPTANCE_RUNBOOK.md",
    "docs/RELEASE_RUNBOOK.md",
    "docs/TROUBLESHOOTING.md",
    "docs/MAINTENANCE_POLICY.md",
    "docs/SECURITY_AND_SECRETS.md",
    "docs/MUSIC_REVIEW_GUIDE.md",
)

SENSITIVE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"githubkey\.txt", re.IGNORECASE),
)


class GAReadinessError(RuntimeError):
    pass


def build_ga_readiness_report(
    *,
    repo_root: Path | str | None = None,
    strict: bool = False,
    allow_dirty: bool = False,
    require_manual_acceptance: bool = False,
    require_audio: bool = False,
    require_audio_campaign: bool = False,
    audio_campaign_id: str | None = None,
    audio_campaign_archive_zip_path: Path | str | None = None,
    audio_campaign_archive_verification_report_path: Path | str | None = None,
    require_audio_campaign_remediation: bool = False,
    audio_campaign_remediation_zip_path: Path | str | None = None,
    audio_campaign_remediation_verification_report_path: Path | str | None = None,
    require_release_audio_certification: bool = False,
    release_audio_certification_zip_path: Path | str | None = None,
    release_audio_certification_verification_report_path: Path | str | None = None,
    require_final_readiness: bool = False,
    final_handoff_verification_report_path: Path | str | None = None,
    release_check_latest_report_path: Path | str | None = None,
    release_check_ga_report_path: Path | str | None = None,
    run_release_checks: bool = False,
    skip_tests: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root or Path.cwd()).resolve()
    checks: list[dict[str, Any]] = []
    source: dict[str, Any] = {
        "repo_root": ".",
        "strict": strict,
        "require_manual_acceptance": require_manual_acceptance,
        "require_audio": require_audio,
        "require_audio_campaign": require_audio_campaign,
        "require_audio_campaign_remediation": require_audio_campaign_remediation,
        "require_release_audio_certification": require_release_audio_certification,
        "audio_campaign_id": audio_campaign_id,
        "require_final_readiness": require_final_readiness,
    }

    version_summary = _version_summary(root)
    _add_check(
        checks,
        "ga.version_consistency",
        "passed" if version_summary.get("consistent") else "failed",
        "blocking",
        "Package version matches pyproject.toml." if version_summary.get("consistent") else "Package version does not match pyproject.toml.",
        version_summary,
    )

    git_summary = _git_summary(root)
    git_status = "passed"
    git_severity = "warning"
    git_message = "Working tree is clean."
    if git_summary.get("state") != "clean":
        git_message = "Working tree is not clean."
        if strict and not allow_dirty:
            git_status = "failed"
            git_severity = "blocking"
        else:
            git_status = "warning"
    _add_check(checks, "ga.git_clean", git_status, git_severity, git_message, git_summary)

    doctor_summary = _doctor_summary(root)
    _add_check(
        checks,
        "ga.doctor",
        "passed" if doctor_summary.get("status") == "passed" else "failed",
        "blocking",
        "Core local setup is usable." if doctor_summary.get("status") == "passed" else "Core local setup has blocking issues.",
        doctor_summary,
    )

    docs_summary = _docs_summary(root)
    _add_check(
        checks,
        "ga.docs_present",
        "passed" if not docs_summary.get("missing") else "failed",
        "blocking",
        "GA/LTS docs are present." if not docs_summary.get("missing") else "Required GA/LTS docs are missing.",
        docs_summary,
    )

    secrets_summary = _secret_summary(root)
    _add_check(
        checks,
        "ga.secret_scan",
        "passed" if not secrets_summary.get("findings") else "failed",
        "blocking",
        "No obvious token or local key-path strings found in GA docs." if not secrets_summary.get("findings") else "Potential secret or local key-path string found.",
        secrets_summary,
    )

    renderer_summary = _renderer_summary(root)
    renderer_status = "passed"
    renderer_severity = "info"
    renderer_message = "Renderer profile is configured." if renderer_summary.get("status") == "configured" else "Renderer profile is not configured."
    if require_audio and renderer_summary.get("status") != "configured":
        renderer_status = "failed"
        renderer_severity = "blocking"
    elif renderer_summary.get("status") != "configured":
        renderer_status = "warning"
        renderer_severity = "warning"
    _add_check(checks, "ga.renderer_audio", renderer_status, renderer_severity, renderer_message, renderer_summary)

    provider_summary = _provider_summary(root)
    _add_check(
        checks,
        "ga.provider",
        "passed" if provider_summary.get("status") in {"configured", "mock", "missing"} else "warning",
        "info",
        "Provider configuration is optional for deterministic local mode.",
        provider_summary,
    )

    acceptance_summary = _acceptance_summary(root)
    acceptance_status = _acceptance_check_status(acceptance_summary, require_manual_acceptance=require_manual_acceptance, require_audio=require_audio)
    _add_check(
        checks,
        "ga.acceptance_manual",
        acceptance_status["status"],
        acceptance_status["severity"],
        acceptance_status["message"],
        acceptance_summary,
    )

    audio_campaign_summary = _audio_campaign_summary(
        audio_campaign_id,
        required=require_audio_campaign,
        archive_zip_path=audio_campaign_archive_zip_path,
        archive_verification_report_path=audio_campaign_archive_verification_report_path,
    )
    _add_check(
        checks,
        "ga.audio_campaign",
        "passed" if audio_campaign_summary.get("status") == "passed" else "failed" if require_audio_campaign else "warning",
        "blocking" if require_audio_campaign else "warning",
        "Audio Campaign governance evidence is passed." if audio_campaign_summary.get("status") == "passed" else "Audio Campaign governance evidence is missing or not passed.",
        audio_campaign_summary,
    )

    remediation_summary = _audio_campaign_remediation_summary(
        required=require_audio_campaign_remediation,
        remediation_zip_path=audio_campaign_remediation_zip_path,
        remediation_verification_report_path=audio_campaign_remediation_verification_report_path,
    )
    _add_check(
        checks,
        "ga.audio_campaign_remediation",
        "passed" if remediation_summary.get("status") == "passed" else "failed" if require_audio_campaign_remediation else "warning",
        "blocking" if require_audio_campaign_remediation else "warning",
        "Audio Campaign remediation evidence is passed." if remediation_summary.get("status") == "passed" else "Audio Campaign remediation evidence is missing or not passed.",
        remediation_summary,
    )

    certification_summary = _release_audio_certification_summary(
        required=require_release_audio_certification,
        certification_zip_path=release_audio_certification_zip_path,
        certification_verification_report_path=release_audio_certification_verification_report_path,
    )
    _add_check(
        checks,
        "ga.release_audio_certification",
        "passed" if certification_summary.get("status") == "passed" else "failed" if require_release_audio_certification else "warning",
        "blocking" if require_release_audio_certification else "warning",
        "Release Audio Certification evidence is passed." if certification_summary.get("status") == "passed" else "Release Audio Certification evidence is missing or not passed.",
        certification_summary,
    )

    latest_summary = _release_check_summary(
        root,
        report_path=release_check_latest_report_path,
        profile="latest",
        run_checks=run_release_checks,
        skip_tests=skip_tests,
    )
    _add_check(
        checks,
        "ga.release_check_latest",
        "passed" if latest_summary.get("status") == "passed" else "warning",
        "warning",
        "latest release-check profile is passed." if latest_summary.get("status") == "passed" else "latest release-check report is missing or not passed.",
        latest_summary,
    )

    ga_summary = _release_check_summary(
        root,
        report_path=release_check_ga_report_path,
        profile="ga",
        run_checks=run_release_checks,
        skip_tests=skip_tests,
    )
    _add_check(
        checks,
        "ga.release_check_ga",
        "passed" if ga_summary.get("status") == "passed" else "warning",
        "warning",
        "ga release-check profile is passed." if ga_summary.get("status") == "passed" else "ga release-check report is missing or not passed.",
        ga_summary,
    )

    final_summary = _final_readiness_summary(final_handoff_verification_report_path)
    final_status = "passed" if final_summary.get("status") == "passed" else "warning"
    final_severity = "warning"
    final_message = "Final Handoff verification report is passed." if final_summary.get("status") == "passed" else "Final Handoff verification report is missing or not passed."
    if require_final_readiness and final_summary.get("status") != "passed":
        final_status = "failed"
        final_severity = "blocking"
    _add_check(checks, "ga.trust_final_readiness", final_status, final_severity, final_message, final_summary)

    blocking_failures = [check for check in checks if check["status"] == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check["status"] == "warning" or check.get("severity") == "warning"]
    status = "blocked" if blocking_failures else "warning" if warnings else "ready"

    report = {
        "schema_version": GA_READINESS_SCHEMA_VERSION,
        "package_type": GA_READINESS_PACKAGE_TYPE,
        "generated_at": _now(),
        "app_version": __version__,
        "status": status,
        "summary": {
            "doctor_status": doctor_summary.get("status", "unknown"),
            "release_check_latest_status": latest_summary.get("status", "unknown"),
            "release_check_ga_status": ga_summary.get("status", "unknown"),
            "acceptance_status": acceptance_summary.get("status", "missing"),
            "audio_campaign_status": audio_campaign_summary.get("status", "missing"),
            "audio_campaign_remediation_status": remediation_summary.get("status", "missing"),
            "release_audio_certification_status": certification_summary.get("status", "missing"),
            "renderer_status": renderer_summary.get("status", "unknown"),
            "provider_status": provider_summary.get("status", "unknown"),
            "trust_final_readiness_status": final_summary.get("status", "missing"),
            "git_status": git_summary.get("state", "unknown"),
        },
        "checks": checks,
        "next_actions": _next_actions(checks),
        "source": source,
    }
    report["integrity_hash"] = ga_readiness_integrity_hash(report)
    return sanitize_ga_report(report)


def ga_readiness_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def ga_readiness_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == ga_readiness_integrity_hash(report)


def write_ga_readiness_report(report: dict[str, Any], path: Path | str = DEFAULT_GA_REPORT_PATH) -> Path:
    target = Path(path)
    write_json(target, sanitize_ga_report(report))
    return target


def read_ga_readiness_report(path: Path | str = DEFAULT_GA_REPORT_PATH, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"GA readiness report not found: {target}")
    return sanitize_ga_report(read_json(target))


def sanitize_ga_report(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_ga_report(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_ga_report(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _add_check(checks: list[dict[str, Any]], check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> None:
    checks.append(
        sanitize_ga_report(
            {
                "check_id": check_id,
                "status": status,
                "severity": severity,
                "message": message,
                "detail": detail or {},
            }
        )
    )


def _version_summary(root: Path) -> dict[str, Any]:
    pyproject_version = "unknown"
    try:
        with (root / "pyproject.toml").open("rb") as file:
            pyproject_version = str((tomllib.load(file).get("project") or {}).get("version") or "unknown")
    except Exception:
        pyproject_version = "unknown"
    return {
        "package_version": __version__,
        "pyproject_version": pyproject_version,
        "consistent": __version__ == pyproject_version and pyproject_version != "unknown",
    }


def _git_summary(root: Path) -> dict[str, Any]:
    try:
        status = subprocess.run(["git", "status", "--short", "--branch"], cwd=root, text=True, capture_output=True, timeout=20)
        lines = [line for line in status.stdout.splitlines() if line.strip()]
        branch = lines[0] if lines else ""
        dirty = any(not line.startswith("## ") for line in lines)
        ahead = "ahead" in branch
        behind = "behind" in branch
        state = "dirty" if dirty else "ahead" if ahead else "behind" if behind else "clean"
        return {"state": state, "branch": branch, "dirty": dirty, "ahead": ahead, "behind": behind}
    except Exception as exc:
        return {"state": "unknown", "error": str(exc)}


def _doctor_summary(root: Path) -> dict[str, Any]:
    cwd_writable = _writable(root)
    runs_writable = _writable(root / "runs")
    status = "passed" if cwd_writable and runs_writable else "failed"
    return {
        "status": status,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "cwd_writable": cwd_writable,
        "runs_writable": runs_writable,
        "deterministic_mode": "ok",
    }


def _docs_summary(root: Path) -> dict[str, Any]:
    present = []
    missing = []
    for rel in REQUIRED_DOCS:
        (present if (root / rel).exists() else missing).append(rel)
    return {"present": present, "missing": missing, "required_count": len(REQUIRED_DOCS)}


def _secret_summary(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for rel in ("README.md", "CHANGELOG.md", *REQUIRED_DOCS):
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                findings.append({"path": rel, "pattern": pattern.pattern})
    return {"findings": findings, "scanned": ["README.md", "CHANGELOG.md", *REQUIRED_DOCS]}


def _renderer_summary(root: Path) -> dict[str, Any]:
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        store = AudioProfileStore(root / ".musicforge" / "audio-profiles")
        try:
            profile = store.get_profile()
        except AudioProfileNotFoundError:
            return {"status": "missing", "profile_id": None}
        return {
            "status": "configured",
            "profile_id": profile.profile_id,
            "engine": profile.engine,
            "enabled": profile.enabled,
            "soundfont_configured": bool(profile.soundfont_path),
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        os.chdir(previous_cwd)


def _provider_summary(root: Path) -> dict[str, Any]:
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        config, _sources = load_provider_config()
        if provider_configured(config):
            status = "mock" if str(config.wire_api).lower() == "mock" else "configured"
        elif config.model or config.base_url or config.api_key:
            status = "incomplete"
        else:
            status = "missing"
        return {"status": status, "wire_api": config.wire_api or "", "model": config.model or ""}
    except ProviderError as exc:
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        return {"status": "unknown", "error": str(exc)}
    finally:
        os.chdir(previous_cwd)


def _acceptance_summary(root: Path) -> dict[str, Any]:
    store = AcceptanceStore(root=root / ".musicforge" / "acceptance")
    candidates: list[dict[str, Any]] = []
    try:
        for suite in store.list_suites(include_archived=True):
            report = store.read_report(suite.suite_id, default={})
            summary = acceptance_report_summary(report)
            if not report:
                continue
            candidates.append(
                {
                    "suite_id": suite.suite_id,
                    "profile_id": suite.profile_id,
                    "status": summary.get("status") or report.get("status") or "unknown",
                    "acceptance_status": summary.get("acceptance_status") or report.get("acceptance_status") or "unknown",
                    "release_ready": bool(summary.get("release_ready") or report.get("release_ready")),
                    "manual_accepted_count": int(summary.get("manual_accepted_count") or report.get("manual_accepted_count") or 0),
                    "synthetic_accepted_count": int(summary.get("synthetic_accepted_count") or report.get("synthetic_accepted_count") or 0),
                    "case_count": int(summary.get("case_count") or report.get("case_count") or 0),
                    "audio_required": bool(summary.get("audio_required") or report.get("audio_required")),
                }
            )
    except Exception as exc:
        return {"status": "unknown", "error": str(exc), "suites": []}
    manual_ready = [item for item in candidates if item["status"] == "passed" and item["manual_accepted_count"] > 0]
    release_ready = [item for item in candidates if item["status"] == "passed" and item["release_ready"]]
    synthetic_only = [item for item in candidates if item["status"] == "passed" and item["synthetic_accepted_count"] > 0 and item["manual_accepted_count"] == 0]
    if manual_ready:
        status = "passed"
    elif synthetic_only:
        status = "synthetic_only"
    elif candidates:
        status = "failed"
    else:
        status = "missing"
    return {
        "status": status,
        "suite_count": len(candidates),
        "manual_ready_count": len(manual_ready),
        "release_ready_count": len(release_ready),
        "synthetic_only_count": len(synthetic_only),
        "latest": candidates[-1] if candidates else {},
    }


def _audio_campaign_summary(
    campaign_id: str | None,
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
) -> dict[str, Any]:
    if not campaign_id:
        return {"status": "missing", "campaign_id": None, "message": "Audio Campaign governance evidence was not provided."}
    try:
        gate = AudioCampaignGovernanceStore().gate(
            str(campaign_id),
            required=required,
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
        )
        return {
            "status": gate.get("status") or "failed",
            "campaign_id": campaign_id,
            "gate": gate,
            "archive_zip_sha256": gate.get("archive_zip_sha256"),
            "archive_verification_hash": gate.get("archive_verification_hash"),
            "case_count": (gate.get("summary") or {}).get("case_count") if isinstance(gate.get("summary"), dict) else None,
            "message": gate.get("message"),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "campaign_id": campaign_id, "error": str(exc)}


def _audio_campaign_remediation_summary(
    *,
    required: bool,
    remediation_zip_path: Path | str | None,
    remediation_verification_report_path: Path | str | None,
) -> dict[str, Any]:
    if remediation_zip_path is None:
        return {"status": "missing", "message": "Audio Campaign remediation package was not provided."}
    try:
        zip_path = Path(remediation_zip_path)
        runtime_report = verify_audio_campaign_remediation_package(zip_path, strict=True, require_passed=required, require_signed=False)
        external_report: dict[str, Any] = {}
        if remediation_verification_report_path is not None:
            external_report = read_json(Path(remediation_verification_report_path))
        status = "passed" if runtime_report.get("status") == "passed" else "failed"
        verification_hash = external_report.get("integrity_hash") if isinstance(external_report, dict) else None
        return {
            "status": status,
            "zip_sha256": runtime_report.get("zip_sha256"),
            "manifest_hash": runtime_report.get("manifest_hash"),
            "verification_hash": verification_hash or runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}


def _release_audio_certification_summary(
    *,
    required: bool,
    certification_zip_path: Path | str | None,
    certification_verification_report_path: Path | str | None,
) -> dict[str, Any]:
    if certification_zip_path is None:
        return {"status": "missing", "message": "Release Audio Certification package was not provided."}
    try:
        zip_path = Path(certification_zip_path)
        runtime_report = verify_release_audio_certification_package(
            zip_path,
            strict=True,
            require_passed=required,
            require_signed=required,
            require_real_audio=required,
            require_manual_review=required,
            require_remediation_when_needed=required,
        )
        external_report: dict[str, Any] = {}
        if certification_verification_report_path is not None:
            external_report = read_json(Path(certification_verification_report_path))
        summary = runtime_report.get("summary") if isinstance(runtime_report.get("summary"), dict) else {}
        return {
            "status": "passed" if runtime_report.get("status") == "passed" else "failed",
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "track_count": summary.get("track_count"),
            "release_id": summary.get("release_id"),
            "summary": summary,
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}


def _acceptance_check_status(summary: dict[str, Any], *, require_manual_acceptance: bool, require_audio: bool) -> dict[str, str]:
    status = str(summary.get("status") or "missing")
    if require_manual_acceptance and status != "passed":
        return {"status": "failed", "severity": "blocking", "message": "Manual acceptance evidence is required and not present."}
    if require_audio and status == "passed" and not bool((summary.get("latest") or {}).get("audio_required")):
        return {"status": "failed", "severity": "blocking", "message": "Audio acceptance evidence is required and the latest accepted suite is not audio-required."}
    if status == "passed":
        return {"status": "passed", "severity": "info", "message": "Manual acceptance evidence is present."}
    if status == "synthetic_only":
        return {"status": "warning", "severity": "warning", "message": "Only synthetic acceptance evidence was found; this is not human listening review."}
    return {"status": "warning", "severity": "warning", "message": "Acceptance evidence is missing or not passed."}


def _release_check_summary(root: Path, *, report_path: Path | str | None, profile: str, run_checks: bool, skip_tests: bool) -> dict[str, Any]:
    if report_path:
        try:
            report = read_json(Path(report_path))
            return {
                "status": "passed" if report.get("ok") else "failed",
                "profile": report.get("profile") or profile,
                "total": (report.get("summary") or {}).get("total"),
                "failed": (report.get("summary") or {}).get("failed"),
                "source": "report",
            }
        except Exception as exc:
            return {"status": "unknown", "profile": profile, "error": str(exc), "source": "report"}
    if run_checks:
        report = run_release_check_matrix(repo_root=root, profile=profile, run_tests=not skip_tests)
        return {
            "status": "passed" if report.ok else "failed",
            "profile": profile,
            "total": len(report.results),
            "failed": sum(1 for result in report.results if not result.ok),
            "source": "runtime",
        }
    return {"status": "unknown", "profile": profile, "source": "not_run"}


def _final_readiness_summary(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {"status": "missing"}
    try:
        report = read_json(Path(path))
        return {
            "status": "passed" if report.get("status") == "passed" else "failed",
            "package_type": report.get("package_type"),
            "zip_sha256": report.get("zip_sha256"),
            "manifest_hash": report.get("manifest_hash"),
        }
    except Exception as exc:
        return {"status": "unknown", "error": str(exc)}


def _next_actions(checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions = []
    for check in checks:
        if check.get("status") == "passed":
            continue
        actions.append(
            {
                "check_id": str(check.get("check_id") or ""),
                "action": _action_for_check(str(check.get("check_id") or "")),
                "reason": str(check.get("message") or ""),
            }
        )
    return actions


def _action_for_check(check_id: str) -> str:
    return {
        "ga.docs_present": "Add or restore the GA/LTS docs under docs/.",
        "ga.secret_scan": "Remove token-like strings or local key-file paths from docs.",
        "ga.git_clean": "Commit or stash local changes before GA release.",
        "ga.acceptance_manual": "Run the manual acceptance runbook and record human listening reviews.",
        "ga.renderer_audio": "Configure a renderer/audio profile before claiming audio readiness.",
        "ga.trust_final_readiness": "Build and verify the Trust Operations Final Handoff package.",
        "ga.release_audio_certification": "Build, sign, and verify the Release Audio Certification package.",
        "ga.release_check_latest": "Run release-check --profile latest and pass the generated report to ga-check.",
        "ga.release_check_ga": "Run release-check --profile ga and pass the generated report to ga-check.",
    }.get(check_id, "Review and repair this GA readiness check.")


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".musicforge-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _redact_text(value: str) -> str:
    text = value
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-...redacted", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_...redacted", text)
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_...redacted", text)
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\n]+", r"C:\\Users\\<user>", text)
    return text
