# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import os as os
import platform as platform
import re as re
import subprocess as subprocess
import sys as sys
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Callable as Callable
import tomllib as tomllib
from song_agent.platform.version import VERSION as __version__
from song_agent.application.policy_compatibility import canonical_ga_policy_id as canonical_ga_policy_id, evaluate_check_policy as evaluate_check_policy, legacy_require_summary as legacy_require_summary, normalized_legacy_require_payload as normalized_legacy_require_payload
from song_agent.domains.quality.audio_profiles import AudioProfileStore as AudioProfileStore, AudioProfileNotFoundError as AudioProfileNotFoundError
from song_agent.domains.quality.audio_campaign_governance import AudioCampaignGovernanceStore as AudioCampaignGovernanceStore
from song_agent.domains.quality.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package as verify_audio_campaign_remediation_package
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.quality.release_audio_regression_verifier import verify_release_audio_regression_package as verify_release_audio_regression_package
from song_agent.domains.quality.release_audio_baseline_governance_verifier import verify_release_audio_baseline_registry_package as verify_release_audio_baseline_registry_package
from song_agent.domains.quality.release_audio_regression_response_verifier import verify_release_audio_regression_response_package as verify_release_audio_regression_response_package
from song_agent.domains.quality.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package as verify_release_audio_quality_observatory_package
from song_agent.domains.quality.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package as verify_release_audio_quality_action_queue_package
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import verify_release_audio_quality_action_queue_signoff_archive_package as verify_release_audio_quality_action_queue_signoff_archive_package
from song_agent.domains.quality.release_audio_command_center_verifier import verify_release_audio_command_center_package as verify_release_audio_command_center_package
from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore, acceptance_report_summary as acceptance_report_summary, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.provider import ProviderError as ProviderError, load_provider_config as load_provider_config, provider_configured as provider_configured
from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE as GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION as GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_hash as ga_readiness_integrity_hash, ga_readiness_integrity_ok as ga_readiness_integrity_ok

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

item = _make_deferred_global('item')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global item, value
    item = namespace.get('item', item)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


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




def _acceptance_summary(root: Path) -> DomainDocument:
    store = AcceptanceStore(root=root / ".musicforge" / "acceptance")
    candidates: list[DomainDocument] = []
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
) -> DomainDocument:
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
) -> DomainDocument:
    if remediation_zip_path is None:
        return {"status": "missing", "message": "Audio Campaign remediation package was not provided."}
    try:
        zip_path = Path(remediation_zip_path)
        runtime_report = verify_audio_campaign_remediation_package(zip_path, strict=True, require_passed=required, require_signed=False)
        external_report: DomainDocument = {}
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
) -> DomainDocument:
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
        external_report: DomainDocument = {}
        if certification_verification_report_path is not None:
            external_report = read_json(Path(certification_verification_report_path))
        summary = _as_document(runtime_report.get("summary"))
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

def _release_audio_timeline_summary(
    *,
    required: bool,
    timeline_zip_path: Path | str | None,
    timeline_verification_report_path: Path | str | None,
    certification_zip_path: Path | str | None = None,
    certification_verification_report_path: Path | str | None = None,
) -> DomainDocument:
    if timeline_zip_path is None:
        return {"status": "missing", "message": "Release Audio Timeline package was not provided."}
    try:
        zip_path = Path(timeline_zip_path)
        runtime_report = verify_release_audio_timeline_package(
            zip_path,
            strict=True,
            require_passed=required,
            require_signed=required,
            require_real_audio=required,
            require_manual_review=required,
            require_current_certification=required,
            release_audio_certification_path=certification_zip_path,
            release_audio_certification_verification_report_path=certification_verification_report_path,
        )
        external_report: DomainDocument = {}
        if timeline_verification_report_path is not None:
            external_report = read_json(Path(timeline_verification_report_path))
        summary = _as_document(runtime_report.get("summary"))
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
            "timeline_id": summary.get("timeline_id"),
            "summary": summary,
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _release_audio_regression_summary(
    *,
    required: bool,
    regression_zip_path: Path | str | None,
    regression_verification_report_path: Path | str | None,
    baseline_timeline_path: Path | str | None = None,
    baseline_timeline_verification_report_path: Path | str | None = None,
    baseline_certification_path: Path | str | None = None,
    baseline_certification_verification_report_path: Path | str | None = None,
    current_timeline_path: Path | str | None = None,
    current_timeline_verification_report_path: Path | str | None = None,
    current_certification_path: Path | str | None = None,
    current_certification_verification_report_path: Path | str | None = None,
) -> DomainDocument:
    if regression_zip_path is None:
        return {"status": "missing", "message": "Release Audio Regression package was not provided."}
    try:
        zip_path = Path(regression_zip_path)
        runtime_report = verify_release_audio_regression_package(
            zip_path,
            strict=True,
            require_passed=required,
            require_signed=required,
            require_current=required,
            require_baseline_current=required,
            baseline_timeline_path=baseline_timeline_path,
            baseline_timeline_verification_report_path=baseline_timeline_verification_report_path,
            baseline_certification_path=baseline_certification_path,
            baseline_certification_verification_report_path=baseline_certification_verification_report_path,
            current_timeline_path=current_timeline_path,
            current_timeline_verification_report_path=current_timeline_verification_report_path,
            current_certification_path=current_certification_path,
            current_certification_verification_report_path=current_certification_verification_report_path,
        )
        external_report: DomainDocument = {}
        if regression_verification_report_path is not None:
            external_report = read_json(Path(regression_verification_report_path))
        summary = _as_document(runtime_report.get("summary"))
        return {
            "status": "passed" if runtime_report.get("status") == "passed" else "failed",
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "release_id": summary.get("release_id"),
            "baseline_release_id": summary.get("baseline_release_id"),
            "summary": summary,
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _release_audio_baseline_governance_summary(
    *,
    required: bool,
    registry_zip_path: Path | str | None,
    registry_verification_report_path: Path | str | None,
) -> DomainDocument:
    if registry_zip_path is None:
        return {"status": "missing", "message": "Release Audio Baseline Registry package was not provided."}
    try:
        zip_path = Path(registry_zip_path)
        runtime_report = verify_release_audio_baseline_registry_package(zip_path, strict=True, require_active=required)
        external_report: DomainDocument = {}
        if registry_verification_report_path is not None:
            external_report = read_json(Path(registry_verification_report_path))
        return {
            "status": "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") else "failed",
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256") or (runtime_report.get("summary") or {}).get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes") or (runtime_report.get("summary") or {}).get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash") or (runtime_report.get("summary") or {}).get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _release_audio_regression_response_summary(
    *,
    required: bool,
    response_zip_path: Path | str | None,
    response_verification_report_path: Path | str | None,
    regression_zip_path: Path | str | None = None,
    regression_verification_report_path: Path | str | None = None,
    baseline_timeline_path: Path | str | None = None,
    baseline_timeline_verification_report_path: Path | str | None = None,
    baseline_certification_path: Path | str | None = None,
    baseline_certification_verification_report_path: Path | str | None = None,
    current_timeline_path: Path | str | None = None,
    current_timeline_verification_report_path: Path | str | None = None,
    current_certification_path: Path | str | None = None,
    current_certification_verification_report_path: Path | str | None = None,
) -> DomainDocument:
    if response_zip_path is None:
        return {"status": "missing", "message": "Release Audio Regression Response package was not provided."}
    try:
        zip_path = Path(response_zip_path)
        current_args = {
            "release_audio_regression_path": regression_zip_path,
            "release_audio_regression_verification_report_path": regression_verification_report_path,
            "baseline_timeline_path": baseline_timeline_path,
            "baseline_timeline_verification_report_path": baseline_timeline_verification_report_path,
            "baseline_certification_path": baseline_certification_path,
            "baseline_certification_verification_report_path": baseline_certification_verification_report_path,
            "current_timeline_path": current_timeline_path,
            "current_timeline_verification_report_path": current_timeline_verification_report_path,
            "current_certification_path": current_certification_path,
            "current_certification_verification_report_path": current_certification_verification_report_path,
        }
        has_current_args = all(value is not None for value in current_args.values())
        if required and not has_current_args:
            return {"status": "failed", "message": "Release Audio Regression Response requires current regression evidence."}
        runtime_report = verify_release_audio_regression_response_package(
            zip_path,
            strict=True,
            require_closed=required,
            require_signed=required,
            require_regression_current=has_current_args,
            release_audio_regression_path=current_args.get("release_audio_regression_path"),
            release_audio_regression_verification_report_path=current_args.get("release_audio_regression_verification_report_path"),
            baseline_timeline_path=current_args.get("baseline_timeline_path"),
            baseline_timeline_verification_report_path=current_args.get("baseline_timeline_verification_report_path"),
            baseline_certification_path=current_args.get("baseline_certification_path"),
            baseline_certification_verification_report_path=current_args.get("baseline_certification_verification_report_path"),
            current_timeline_path=current_args.get("current_timeline_path"),
            current_timeline_verification_report_path=current_args.get("current_timeline_verification_report_path"),
            current_certification_path=current_args.get("current_certification_path"),
            current_certification_verification_report_path=current_args.get("current_certification_verification_report_path"),
        )
        external_report: DomainDocument = {}
        if response_verification_report_path is not None:
            external_report = read_json(Path(response_verification_report_path))
        return {
            "status": "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") else "failed",
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256") or (runtime_report.get("summary") or {}).get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes") or (runtime_report.get("summary") or {}).get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash") or (runtime_report.get("summary") or {}).get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _release_audio_quality_observatory_summary(
    *,
    required: bool,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
    require_no_critical_risk: bool,
) -> DomainDocument:
    if observatory_zip_path is None:
        return {"status": "missing", "message": "Release Audio Quality Observatory package was not provided."}
    try:
        zip_path = Path(observatory_zip_path)
        runtime_report = verify_release_audio_quality_observatory_package(
            zip_path,
            strict=True,
            require_current_evidence=required,
            evidence_root=evidence_root,
            require_no_critical_risk=require_no_critical_risk,
        )
        external_report: DomainDocument = {}
        if observatory_verification_report_path is not None:
            external_report = read_json(Path(observatory_verification_report_path))
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") else "failed"
        return {
            "status": status,
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256") or (runtime_report.get("summary") or {}).get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes") or (runtime_report.get("summary") or {}).get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash") or (runtime_report.get("summary") or {}).get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _release_audio_quality_action_queue_summary(
    *,
    required: bool,
    queue_zip_path: Path | str | None,
    queue_verification_report_path: Path | str | None,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> DomainDocument:
    if queue_zip_path is None:
        return {"status": "missing", "message": "Release Audio Quality Action Queue package was not provided."}
    try:
        zip_path = Path(queue_zip_path)
        runtime_report = verify_release_audio_quality_action_queue_package(
            zip_path,
            strict=True,
            require_current_observatory=required,
            observatory_zip_path=observatory_zip_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
            require_no_blocking=True,
        )
        external_report: DomainDocument = {}
        if queue_verification_report_path is not None:
            external_report = read_json(Path(queue_verification_report_path))
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") else "failed"
        return {
            "status": status,
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_report.get("zip_sha256") or (runtime_report.get("summary") or {}).get("zip_sha256"),
            "zip_size_bytes": runtime_report.get("zip_size_bytes") or (runtime_report.get("summary") or {}).get("zip_size_bytes"),
            "manifest_hash": runtime_report.get("manifest_hash") or (runtime_report.get("summary") or {}).get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if isinstance(external_report, dict) else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if isinstance(external_report, dict) else None,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}
