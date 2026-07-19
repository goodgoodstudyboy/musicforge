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

key = _make_deferred_global('key')
result = _make_deferred_global('result')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global key, result, value
    key = namespace.get('key', key)
    result = namespace.get('result', result)
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




def _unified_release_program_continuity_acceptance_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    kit_zip_path: Path | str | None,
    kit_verification_report_path: Path | str | None,
) -> DomainDocument:
    if archive_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Continuity Acceptance Archive ZIP was not provided."}
    if required and verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity Acceptance requires a verification report."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import verify_unified_release_program_continuity_acceptance_package

        runtime_report = verify_unified_release_program_continuity_acceptance_package(
            archive_zip_path,
            strict=True,
            require_current_kit=True,
            require_signed=True,
            require_quorum=True,
            continuity_kit_path=kit_zip_path,
            continuity_kit_verification_report_path=kit_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
        external_report: DomainDocument = {}
        if verification_report_path is not None:
            external_report = read_json(Path(verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        return {
            "status": status,
            "zip_sha256": runtime_fp.get("zip_sha256"),
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

def _unified_release_program_continuity_command_center_summary(
    *,
    required: bool,
    command_center_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> DomainDocument:
    if command_center_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Continuity Command Center ZIP was not provided."}
    if required and verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity Command Center requires a verification report."}
    if required and external_evidence_manifest_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity Command Center requires an external evidence manifest."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_package,
        )

        runtime_report = verify_unified_release_program_continuity_command_center_package(
            command_center_zip_path,
            strict=True,
            deep=True,
            require_ready=True,
            evidence_manifest_path=external_evidence_manifest_path,
        )
        external_report: DomainDocument = {}
        if verification_report_path is not None:
            external_report = read_json(Path(verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        external_integrity_ok = not external_report or external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        external_package_type_ok = not external_report or external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        zip_size_binding_ok = not external_report or int(external_fp.get("zip_size_bytes") or -1) == int(runtime_fp.get("zip_size_bytes") or -2)
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and external_package_type_ok and zip_binding_ok and zip_size_binding_ok and manifest_binding_ok else "failed"
        return {
            "status": status,
            "zip_sha256": runtime_fp.get("zip_sha256"),
            "zip_size_bytes": runtime_fp.get("zip_size_bytes"),
            "manifest_hash": runtime_fp.get("manifest_hash"),
            "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"),
            "runtime_verification_status": runtime_report.get("status"),
            "external_verification_status": external_report.get("status") if external_report else None,
            "external_integrity_ok": external_integrity_ok,
            "external_package_type_ok": external_package_type_ok,
            "zip_binding_ok": zip_binding_ok,
            "zip_size_binding_ok": zip_size_binding_ok,
            "manifest_binding_ok": manifest_binding_ok,
            "external_evidence_manifest_required": bool(external_evidence_manifest_path),
            "blockers": runtime_report.get("blockers", []),
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_release_program_continuity_command_center_signoff_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> DomainDocument:
    required_paths = (
        archive_zip_path,
        verification_report_path,
        signoff_binding_path,
        command_center_zip_path,
        command_center_verification_report_path,
        external_evidence_manifest_path,
    )
    if not archive_zip_path:
        return {"status": "missing", "message": "Continuity Command Center Signoff Archive was not provided."}
    if required and not all(required_paths):
        return {"status": "failed", "message": "Continuity Command Center signoff requires Archive, verification report, binding, Command Center, and evidence manifest."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import (
            COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_signoff_package,
        )

        runtime = verify_unified_release_program_continuity_command_center_signoff_package(
            archive_zip_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=signoff_binding_path,
            command_center_zip_path=command_center_zip_path,
            command_center_verification_report_path=command_center_verification_report_path,
            command_center_external_evidence_manifest_path=external_evidence_manifest_path,
        )
        external = read_json(Path(verification_report_path)) if verification_report_path else {}
        integrity_ok = bool(external) and external.get("integrity_hash") == stable_hash({key: value for key, value in external.items() if key != "integrity_hash"})
        package_type_ok = external.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE
        binding_ok = external.get("zip_sha256") == runtime.get("zip_sha256") and external.get("manifest_hash") == runtime.get("manifest_hash")
        status = "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" and integrity_ok and package_type_ok and binding_ok else "failed"
        return {
            "status": status,
            "zip_sha256": runtime.get("zip_sha256"),
            "zip_size_bytes": runtime.get("zip_size_bytes"),
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": external.get("integrity_hash"),
            "runtime_verification_status": runtime.get("status"),
            "external_verification_status": external.get("status"),
            "external_integrity_ok": integrity_ok,
            "external_package_type_ok": package_type_ok,
            "binding_ok": binding_ok,
            "blockers": runtime.get("blockers") or [],
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_release_program_continuity_command_center_acceptance_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    acceptance_signoff_binding_path: Path | str | None,
    review_pack_path: Path | str | None,
    review_pack_verification_report_path: Path | str | None,
    accepted_evidence_dir: Path | str | None,
    response_proof_dir: Path | str | None,
    signoff_archive_path: Path | str | None,
    signoff_archive_verification_report_path: Path | str | None,
    final_handoff_path: Path | str | None,
    final_handoff_verification_report_path: Path | str | None,
    command_center_signoff_binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    command_center_evidence_manifest_path: Path | str | None,
) -> DomainDocument:
    required_paths = (
        archive_zip_path,
        verification_report_path,
        acceptance_signoff_binding_path,
        review_pack_path,
        review_pack_verification_report_path,
        accepted_evidence_dir,
        response_proof_dir,
        signoff_archive_path,
        signoff_archive_verification_report_path,
        final_handoff_path,
        final_handoff_verification_report_path,
        command_center_signoff_binding_path,
        command_center_path,
        command_center_verification_report_path,
        command_center_evidence_manifest_path,
    )
    if not archive_zip_path:
        return {"status": "missing", "message": "Receiver Acceptance Archive was not provided."}
    if required and not all(required_paths):
        return {"status": "failed", "message": "Receiver Acceptance requires Archive, external proof roots, and current v12.10 evidence."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import (
            ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_package,
        )

        runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
            archive_zip_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=acceptance_signoff_binding_path,
            review_pack_path=review_pack_path,
            review_pack_verification_report_path=review_pack_verification_report_path,
            accepted_evidence_dir=accepted_evidence_dir,
            response_proof_dir=response_proof_dir,
            command_center_signoff_archive_path=signoff_archive_path,
            command_center_signoff_archive_verification_report_path=signoff_archive_verification_report_path,
            command_center_final_handoff_path=final_handoff_path,
            command_center_final_handoff_verification_report_path=final_handoff_verification_report_path,
            command_center_signoff_binding_path=command_center_signoff_binding_path,
            command_center_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
            command_center_evidence_manifest_path=command_center_evidence_manifest_path,
        )
        external = read_json(Path(verification_report_path)) if verification_report_path else {}
        integrity_ok = bool(external) and external.get("integrity_hash") == stable_hash({key: value for key, value in external.items() if key != "integrity_hash"})
        package_type_ok = external.get("package_type") == ARCHIVE_VERIFICATION_PACKAGE_TYPE
        binding_ok = external.get("zip_sha256") == runtime.get("zip_sha256") and external.get("manifest_hash") == runtime.get("manifest_hash")
        status = "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" and integrity_ok and package_type_ok and binding_ok else "failed"
        return {
            "status": status,
            "zip_sha256": runtime.get("zip_sha256"),
            "zip_size_bytes": runtime.get("zip_size_bytes"),
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": external.get("integrity_hash"),
            "runtime_verification_status": runtime.get("status"),
            "external_verification_status": external.get("status"),
            "external_integrity_ok": integrity_ok,
            "external_package_type_ok": package_type_ok,
            "binding_ok": binding_ok,
            "blockers": runtime.get("blockers") or [],
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_release_program_continuity_command_center_acceptance_change_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    acceptance_archive_path: Path | str | None,
    acceptance_verification_report_path: Path | str | None,
    acceptance_signoff_binding_path: Path | str | None,
    previous_acceptance_root: Path | str | None,
) -> DomainDocument:
    if not archive_zip_path:
        return {"status": "missing", "message": "Receiver Acceptance Change Control Archive was not provided."}
    required_paths = (
        archive_zip_path,
        verification_report_path,
        acceptance_archive_path,
        acceptance_verification_report_path,
        acceptance_signoff_binding_path,
    )
    if required and not all(required_paths):
        return {"status": "failed", "message": "Receiver Acceptance Change Control requires current Archive, verification report, and signoff binding."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_change_package,
        )

        runtime = verify_unified_release_program_continuity_command_center_acceptance_change_package(
            archive_zip_path,
            strict=True,
            require_current_acceptance=True,
            acceptance_archive_path=acceptance_archive_path,
            acceptance_verification_report_path=acceptance_verification_report_path,
            acceptance_signoff_binding_path=acceptance_signoff_binding_path,
            previous_acceptance_root=previous_acceptance_root,
            require_reset_proofs=True,
        )
        external = read_json(Path(verification_report_path)) if verification_report_path else {}
        integrity_ok = bool(external) and external.get("integrity_hash") == stable_hash(
            {key: value for key, value in external.items() if key != "integrity_hash"}
        )
        binding_ok = (
            external.get("zip_sha256") == runtime.get("zip_sha256")
            and external.get("manifest_hash") == runtime.get("manifest_hash")
        )
        status = "passed" if (
            runtime.get("status") == "passed"
            and external.get("status") == "passed"
            and external.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE
            and integrity_ok
            and binding_ok
        ) else "failed"
        return {
            "status": status,
            "zip_sha256": runtime.get("zip_sha256"),
            "zip_size_bytes": runtime.get("zip_size_bytes"),
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": external.get("integrity_hash"),
            "verification_report_hash": external.get("integrity_hash"),
            "current_generation": (runtime.get("summary") or {}).get("current_generation"),
            "reset_count": (runtime.get("summary") or {}).get("reset_count"),
            "blockers": runtime.get("blockers") or [],
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _verification_fingerprint(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
    }

def _acceptance_check_status(summary: DomainDocument, *, require_manual_acceptance: bool, require_audio: bool) -> dict[str, str]:
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

def _release_check_summary(
    root: Path,
    *,
    report_path: Path | str | None,
    profile: str,
    run_checks: bool,
    skip_tests: bool,
    executor: Callable[..., object] | None,
) -> DomainDocument:
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
        if executor is None:
            return {"status": "failed", "profile": profile, "error": "release-check executor is required", "source": "runtime"}
        report = executor(repo_root=root, profile=profile, run_tests=not skip_tests)
        return {
            "status": "passed" if report.ok else "failed",
            "profile": profile,
            "total": len(report.results),
            "failed": sum(1 for result in report.results if not result.ok),
            "source": "runtime",
        }
    return {"status": "unknown", "profile": profile, "source": "not_run"}

def _final_readiness_summary(path: Path | str | None) -> DomainDocument:
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

def _next_actions(checks: list[DomainDocument]) -> list[dict[str, str]]:
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
        "ga.release_audio_timeline": "Build, sign, and verify the Release Audio Timeline package.",
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
