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

_verification_fingerprint = _make_deferred_global('_verification_fingerprint')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global _verification_fingerprint, key, value
    _verification_fingerprint = namespace.get('_verification_fingerprint', _verification_fingerprint)
    key = namespace.get('key', key)
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




def _release_audio_quality_action_queue_signoff_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    queue_zip_path: Path | str | None,
    queue_verification_report_path: Path | str | None,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> DomainDocument:
    if archive_zip_path is None:
        return {"status": "missing", "message": "Release Audio Quality Action Queue signoff archive was not provided."}
    try:
        zip_path = Path(archive_zip_path)
        runtime_report = verify_release_audio_quality_action_queue_signoff_archive_package(
            zip_path,
            strict=True,
            require_current_queue=required,
            require_signed=required,
            queue_zip_path=queue_zip_path,
            queue_verification_report_path=queue_verification_report_path,
            observatory_zip_path=observatory_zip_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
            require_no_unresolved_manual=True,
        )
        external_report: DomainDocument = {}
        if archive_verification_report_path is not None:
            external_report = read_json(Path(archive_verification_report_path))
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

def _release_audio_command_center_summary(
    *,
    required: bool,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    certification_zip_path: Path | str | None,
    certification_verification_report_path: Path | str | None,
    timeline_zip_path: Path | str | None,
    timeline_verification_report_path: Path | str | None,
    regression_zip_path: Path | str | None,
    regression_verification_report_path: Path | str | None,
    baseline_registry_zip_path: Path | str | None,
    baseline_registry_verification_report_path: Path | str | None,
    regression_response_zip_path: Path | str | None,
    regression_response_verification_report_path: Path | str | None,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    action_queue_zip_path: Path | str | None,
    action_queue_verification_report_path: Path | str | None,
    action_queue_signoff_archive_path: Path | str | None,
    action_queue_signoff_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> DomainDocument:
    if command_center_zip_path is None:
        return {"status": "missing", "message": "Release Audio Command Center package was not provided."}
    try:
        zip_path = Path(command_center_zip_path)
        runtime_report = verify_release_audio_command_center_package(
            zip_path,
            strict=True,
            require_ready=required,
            certification_zip_path=certification_zip_path,
            certification_verification_report_path=certification_verification_report_path,
            timeline_zip_path=timeline_zip_path,
            timeline_verification_report_path=timeline_verification_report_path,
            regression_zip_path=regression_zip_path,
            regression_verification_report_path=regression_verification_report_path,
            baseline_registry_zip_path=baseline_registry_zip_path,
            baseline_registry_verification_report_path=baseline_registry_verification_report_path,
            regression_response_zip_path=regression_response_zip_path,
            regression_response_verification_report_path=regression_response_verification_report_path,
            observatory_zip_path=observatory_zip_path,
            observatory_verification_report_path=observatory_verification_report_path,
            action_queue_zip_path=action_queue_zip_path,
            action_queue_verification_report_path=action_queue_verification_report_path,
            action_queue_signoff_archive_path=action_queue_signoff_archive_path,
            action_queue_signoff_verification_report_path=action_queue_signoff_verification_report_path,
            evidence_root=evidence_root,
        )
        external_report: DomainDocument = {}
        if command_center_verification_report_path is not None:
            external_report = read_json(Path(command_center_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = (
            "passed"
            if runtime_report.get("status") == "passed"
            and (not external_report or external_report.get("status") == "passed")
            and external_integrity_ok
            and zip_binding_ok
            and manifest_binding_ok
            else "failed"
        )
        return {
            "status": status,
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_fp.get("zip_sha256"),
            "zip_size_bytes": runtime_fp.get("zip_size_bytes"),
            "manifest_hash": runtime_fp.get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if external_report else None,
            "external_integrity_ok": external_integrity_ok,
            "zip_binding_ok": zip_binding_ok,
            "manifest_binding_ok": manifest_binding_ok,
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_summary(
    *,
    required: bool,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    release_zip_path: Path | str | None,
    release_verification_report_path: Path | str | None,
    release_audio_command_center_zip_path: Path | str | None,
    release_audio_command_center_verification_report_path: Path | str | None,
    distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None,
    distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None,
    submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    release_operations_zip_path: Path | str | None,
    release_operations_verification_report_path: Path | str | None,
    trust_operations_hub_zip_path: Path | str | None,
    trust_operations_hub_verification_report_path: Path | str | None,
    public_trust_center_zip_path: Path | str | None,
    public_trust_center_verification_report_path: Path | str | None,
    maintenance_backup_zip_path: Path | str | None,
    maintenance_backup_verification_report_path: Path | str | None,
    ga_readiness_report_path: Path | str | None,
    release_check_report_path: Path | str | None,
) -> DomainDocument:
    if command_center_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center package was not provided."}
    try:
        from song_agent.domains.program.unified_command_center import evidence_to_verifier_kwargs as unified_command_center_evidence_to_kwargs
        from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package

        zip_path = Path(command_center_zip_path)
        evidence: DomainDocument = {
            "release": {"zip": release_zip_path, "verification_report": release_verification_report_path},
            "audio-command-center": {
                "zip": release_audio_command_center_zip_path,
                "verification_report": release_audio_command_center_verification_report_path,
            },
            "distribution": {"zips": list(distribution_zip_paths or []), "verification_reports": list(distribution_verification_report_paths or [])},
            "submission": {"zips": list(submission_zip_paths or []), "verification_reports": list(submission_verification_report_paths or [])},
            "operations": {"zip": release_operations_zip_path, "verification_report": release_operations_verification_report_path},
            "trust-operations-hub": {"zip": trust_operations_hub_zip_path, "verification_report": trust_operations_hub_verification_report_path},
            "public-trust-center": {"zip": public_trust_center_zip_path, "verification_report": public_trust_center_verification_report_path},
            "maintenance": {"zip": maintenance_backup_zip_path, "verification_report": maintenance_backup_verification_report_path},
            "ga-readiness": {"report": ga_readiness_report_path},
            "release-check": {"report": release_check_report_path},
        }
        runtime_report = verify_unified_command_center_package(
            zip_path,
            strict=True,
            require_ready=required,
            **unified_command_center_evidence_to_kwargs(evidence),
        )
        external_report: DomainDocument = {}
        if command_center_verification_report_path is not None:
            external_report = read_json(Path(command_center_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = (
            "passed"
            if runtime_report.get("status") == "passed"
            and (not external_report or external_report.get("status") == "passed")
            and external_integrity_ok
            and zip_binding_ok
            and manifest_binding_ok
            else "failed"
        )
        return {
            "status": status,
            "package_type": runtime_report.get("package_type"),
            "zip_sha256": runtime_fp.get("zip_sha256"),
            "zip_size_bytes": runtime_fp.get("zip_size_bytes"),
            "manifest_hash": runtime_fp.get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if external_report else None,
            "external_integrity_ok": external_integrity_ok,
            "zip_binding_ok": zip_binding_ok,
            "manifest_binding_ok": manifest_binding_ok,
            "blockers": runtime_report.get("blockers", []),
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_archive_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if archive_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Archive package was not provided."}
    if required and (command_center_zip_path is None or command_center_verification_report_path is None):
        return {"status": "failed", "message": "Unified Command Center Archive requires current Unified Command Center ZIP and verification report."}
    try:
        from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package

        runtime_report = verify_unified_command_center_archive_package(
            archive_zip_path,
            strict=True,
            require_signed=required,
            require_current_ucc=bool(command_center_zip_path and command_center_verification_report_path),
            command_center_zip_path=command_center_zip_path,
            command_center_verification_report_path=command_center_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
        external_report: DomainDocument = {}
        if archive_verification_report_path is not None:
            external_report = read_json(Path(archive_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        return {"status": status, "zip_sha256": runtime_fp.get("zip_sha256"), "manifest_hash": runtime_fp.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"), "runtime_verification_status": runtime_report.get("status"), "external_verification_status": external_report.get("status") if external_report else None, "external_integrity_ok": external_integrity_ok, "zip_binding_ok": zip_binding_ok, "manifest_binding_ok": manifest_binding_ok, "blockers": runtime_report.get("blockers", []), "summary": runtime_report.get("summary", {})}
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_handoff_summary(
    *,
    required: bool,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
) -> DomainDocument:
    if handoff_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Handoff package was not provided."}
    if required and (archive_zip_path is None or archive_verification_report_path is None):
        return {"status": "failed", "message": "Unified Command Center Handoff requires current Archive ZIP and verification report."}
    try:
        from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package

        runtime_report = verify_unified_command_center_handoff_package(
            handoff_zip_path,
            strict=True,
            require_archive=bool(archive_zip_path and archive_verification_report_path),
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
        )
        external_report: DomainDocument = {}
        if handoff_verification_report_path is not None:
            external_report = read_json(Path(handoff_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        return {"status": status, "zip_sha256": runtime_fp.get("zip_sha256"), "manifest_hash": runtime_fp.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"), "runtime_verification_status": runtime_report.get("status"), "external_verification_status": external_report.get("status") if external_report else None, "external_integrity_ok": external_integrity_ok, "zip_binding_ok": zip_binding_ok, "manifest_binding_ok": manifest_binding_ok, "blockers": runtime_report.get("blockers", []), "summary": runtime_report.get("summary", {})}
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_continuous_review_summary(
    *,
    required: bool,
    review_zip_path: Path | str | None,
    review_verification_report_path: Path | str | None,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if review_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Continuous Review package was not provided."}
    if required and review_verification_report_path is None:
        return {"status": "failed", "message": "Unified Command Center Continuous Review requires a verification report."}
    if required and (archive_zip_path is None or archive_verification_report_path is None or handoff_zip_path is None or handoff_verification_report_path is None or command_center_zip_path is None or command_center_verification_report_path is None):
        return {"status": "failed", "message": "Unified Command Center Continuous Review requires current UCC, Archive, and Handoff evidence."}
    try:
        from song_agent.domains.program.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package

        runtime_report = verify_unified_command_center_continuous_review_package(
            review_zip_path,
            strict=True,
            require_clear=required,
            require_recovery_drill=required,
            require_current_review=required,
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_zip_path,
            handoff_verification_report_path=handoff_verification_report_path,
            command_center_zip_path=command_center_zip_path,
            command_center_verification_report_path=command_center_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
        external_report: DomainDocument = {}
        if review_verification_report_path is not None:
            external_report = read_json(Path(review_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        from song_agent.domains.delivery.releases import stable_hash as release_stable_hash

        external_integrity_ok = not external_report or external_report.get("integrity_hash") == release_stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        return {"status": status, "zip_sha256": runtime_fp.get("zip_sha256"), "manifest_hash": runtime_fp.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"), "runtime_verification_status": runtime_report.get("status"), "external_verification_status": external_report.get("status") if external_report else None, "external_integrity_ok": external_integrity_ok, "zip_binding_ok": zip_binding_ok, "manifest_binding_ok": manifest_binding_ok, "blockers": runtime_report.get("blockers", []), "summary": runtime_report.get("summary", {})}
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_drift_response_summary(
    *,
    required: bool,
    response_zip_path: Path | str | None,
    response_verification_report_path: Path | str | None,
    source_review_zip_path: Path | str | None,
    source_review_verification_report_path: Path | str | None,
    recheck_review_zip_path: Path | str | None,
    recheck_review_verification_report_path: Path | str | None,
    change_request_binding_report_path: Path | str | None,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if response_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Drift Response package was not provided."}
    if required and response_verification_report_path is None:
        return {"status": "failed", "message": "Unified Command Center Drift Response requires a verification report."}
    if required and (source_review_zip_path is None or source_review_verification_report_path is None or recheck_review_zip_path is None or recheck_review_verification_report_path is None or change_request_binding_report_path is None):
        return {"status": "failed", "message": "Unified Command Center Drift Response requires source/recheck Continuous Review evidence and external Change Request proof."}
    try:
        from song_agent.domains.program.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package

        runtime_report = verify_unified_command_center_drift_response_package(
            response_zip_path,
            strict=True,
            require_closed=required,
            require_recheck_clear=required,
            require_current_review=required,
            source_review_zip_path=source_review_zip_path,
            source_review_verification_report_path=source_review_verification_report_path,
            recheck_review_zip_path=recheck_review_zip_path,
            recheck_review_verification_report_path=recheck_review_verification_report_path,
            change_request_binding_report_path=change_request_binding_report_path,
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_zip_path,
            handoff_verification_report_path=handoff_verification_report_path,
            command_center_zip_path=command_center_zip_path,
            command_center_verification_report_path=command_center_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
        external_report: DomainDocument = {}
        if response_verification_report_path is not None:
            external_report = read_json(Path(response_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        from song_agent.domains.delivery.releases import stable_hash as release_stable_hash

        external_integrity_ok = not external_report or external_report.get("integrity_hash") == release_stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        return {"status": status, "zip_sha256": runtime_fp.get("zip_sha256"), "manifest_hash": runtime_fp.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"), "runtime_verification_status": runtime_report.get("status"), "external_verification_status": external_report.get("status") if external_report else None, "external_integrity_ok": external_integrity_ok, "zip_binding_ok": zip_binding_ok, "manifest_binding_ok": manifest_binding_ok, "blockers": runtime_report.get("blockers", []), "summary": runtime_report.get("summary", {})}
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}
