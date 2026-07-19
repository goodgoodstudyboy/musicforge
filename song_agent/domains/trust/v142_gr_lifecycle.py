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




def _unified_command_center_evidence_review_summary(
    *,
    required: bool,
    review_zip_path: Path | str | None,
    review_verification_report_path: Path | str | None,
    require_accepted: bool,
    acceptance_zip_path: Path | str | None,
    acceptance_verification_report_path: Path | str | None,
    acceptance_response_verification_report_path: Path | str | None,
    ucc_zip_path: Path | str | None,
    ucc_verification_report_path: Path | str | None,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    continuous_review_zip_path: Path | str | None,
    continuous_review_verification_report_path: Path | str | None,
    drift_response_zip_path: Path | str | None,
    drift_response_verification_report_path: Path | str | None,
    source_review_zip_path: Path | str | None,
    source_review_verification_report_path: Path | str | None,
    recheck_review_zip_path: Path | str | None,
    recheck_review_verification_report_path: Path | str | None,
    drift_change_request_binding_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    ga_readiness_report_path: Path | str | None,
    release_check_report_path: Path | str | None,
) -> DomainDocument:
    if review_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Evidence Review package was not provided."}
    if required and review_verification_report_path is None:
        return {"status": "failed", "message": "Unified Command Center Evidence Review requires a verification report."}
    if require_accepted and (acceptance_zip_path is None or acceptance_verification_report_path is None):
        return {"status": "failed", "message": "Unified Command Center Evidence Review accepted response evidence is required."}
    try:
        from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package

        runtime_report = verify_unified_command_center_evidence_review_package(
            review_zip_path,
            strict=True,
            require_replay_passed=required,
            ucc_zip_path=ucc_zip_path,
            ucc_verification_report_path=ucc_verification_report_path,
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_zip_path,
            handoff_verification_report_path=handoff_verification_report_path,
            continuous_review_zip_path=continuous_review_zip_path,
            continuous_review_verification_report_path=continuous_review_verification_report_path,
            drift_response_zip_path=drift_response_zip_path,
            drift_response_verification_report_path=drift_response_verification_report_path,
            source_review_zip_path=source_review_zip_path,
            source_review_verification_report_path=source_review_verification_report_path,
            recheck_review_zip_path=recheck_review_zip_path,
            recheck_review_verification_report_path=recheck_review_verification_report_path,
            drift_change_request_binding_report_path=drift_change_request_binding_report_path,
            signoff_binding_path=signoff_binding_path,
            ga_readiness_report_path=ga_readiness_report_path,
            release_check_report_path=release_check_report_path,
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
        acceptance_summary: DomainDocument = {}
        if require_accepted and acceptance_zip_path and acceptance_verification_report_path:
            acceptance_runtime = verify_unified_command_center_evidence_review_acceptance_package(
                acceptance_zip_path,
                strict=True,
                require_accepted=True,
                review_pack_path=review_zip_path,
                review_pack_verification_report_path=review_verification_report_path,
                response_verification_report_path=acceptance_response_verification_report_path,
            )
            acceptance_external = read_json(Path(acceptance_verification_report_path))
            acceptance_summary = {
                "runtime_status": acceptance_runtime.get("status"),
                "external_status": acceptance_external.get("status"),
                "verification_hash": acceptance_external.get("integrity_hash"),
            }
            if acceptance_runtime.get("status") != "passed" or acceptance_external.get("status") != "passed":
                status = "failed"
        return {"status": status, "zip_sha256": runtime_fp.get("zip_sha256"), "manifest_hash": runtime_fp.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash") if external_report else runtime_report.get("integrity_hash"), "runtime_verification_status": runtime_report.get("status"), "external_verification_status": external_report.get("status") if external_report else None, "external_integrity_ok": external_integrity_ok, "zip_binding_ok": zip_binding_ok, "manifest_binding_ok": manifest_binding_ok, "acceptance": acceptance_summary, "blockers": runtime_report.get("blockers", []), "summary": runtime_report.get("summary", {})}
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_command_center_reviewer_decision_board_summary(
    *,
    required: bool,
    board_zip_path: Path | str | None,
    board_verification_report_path: Path | str | None,
    require_signed: bool,
    require_quorum: bool,
    evidence_review_zip_path: Path | str | None,
    evidence_review_verification_report_path: Path | str | None,
    accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None,
    accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
) -> DomainDocument:
    if board_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center Reviewer Decision Board archive was not provided."}
    if required and board_verification_report_path is None:
        return {"status": "failed", "message": "Unified Command Center Reviewer Decision Board requires a verification report."}
    try:
        from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import verify_unified_command_center_reviewer_decision_board_package

        runtime_report = verify_unified_command_center_reviewer_decision_board_package(
            board_zip_path,
            strict=True,
            require_signed=require_signed or required,
            require_quorum=require_quorum or required,
            evidence_review_path=evidence_review_zip_path,
            evidence_review_verification_report_path=evidence_review_verification_report_path,
            accepted_evidence_paths=_as_list(accepted_evidence_zip_paths or []),
            accepted_evidence_verification_report_paths=_as_list(accepted_evidence_verification_report_paths or []),
            accepted_evidence_response_verification_report_paths=_as_list(accepted_evidence_response_verification_report_paths or []),
        )
        external_report: DomainDocument = {}
        if board_verification_report_path is not None:
            external_report = read_json(Path(board_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        from song_agent.domains.delivery.releases import stable_hash as release_stable_hash

        external_integrity_ok = not external_report or external_report.get("integrity_hash") == release_stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
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

def _unified_release_program_handoff_summary(
    *,
    required: bool,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
    handoff_signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if handoff_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Handoff archive was not provided."}
    if required and handoff_verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Handoff requires a verification report."}
    try:
        from song_agent.domains.program.unified_release_program_handoff_verifier import verify_unified_release_program_handoff_package

        runtime_report = verify_unified_release_program_handoff_package(
            handoff_zip_path,
            strict=True,
            require_current=True,
            require_accepted=True,
            require_signed=True,
            external_evidence_manifest_path=external_evidence_manifest_path,
            handoff_signoff_binding_path=handoff_signoff_binding_path,
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

def _unified_release_program_vault_summary(
    *,
    required: bool,
    vault_zip_path: Path | str | None,
    vault_verification_report_path: Path | str | None,
    vault_anchor_path: Path | str | None,
) -> DomainDocument:
    if vault_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Evidence Vault ZIP was not provided."}
    if required and vault_verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Evidence Vault requires a verification report."}
    if required and vault_anchor_path is None:
        return {"status": "failed", "message": "Unified Release Program Evidence Vault requires an external anchor."}
    try:
        from song_agent.domains.program.unified_release_program_vault_verifier import verify_unified_release_program_vault_package

        runtime_report = verify_unified_release_program_vault_package(
            vault_zip_path,
            strict=True,
            deep=True,
            require_anchor=True,
            vault_anchor_path=vault_anchor_path,
        )
        external_report: DomainDocument = {}
        if vault_verification_report_path is not None:
            external_report = read_json(Path(vault_verification_report_path))
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

def _unified_release_program_vault_operations_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if archive_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Vault Operations archive ZIP was not provided."}
    if required and archive_verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Vault Operations requires a verification report."}
    if required and signoff_binding_path is None:
        return {"status": "failed", "message": "Unified Release Program Vault Operations requires a signoff binding."}
    try:
        from song_agent.domains.program.unified_release_program_vault_operations_verifier import verify_unified_release_program_vault_operations_package

        runtime_report = verify_unified_release_program_vault_operations_package(
            archive_zip_path,
            strict=True,
            deep=True,
            require_signed=True,
            require_current_vault=True,
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

def _unified_release_program_continuity_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    vault_operations_archive_path: Path | str | None,
    vault_operations_verification_report_path: Path | str | None,
    vault_operations_signoff_binding_path: Path | str | None,
) -> DomainDocument:
    if archive_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Continuity archive ZIP was not provided."}
    if required and archive_verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity requires a verification report."}
    if required and signoff_binding_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity requires a signoff binding."}
    if required and (vault_operations_archive_path is None or vault_operations_verification_report_path is None or vault_operations_signoff_binding_path is None):
        return {"status": "failed", "message": "Unified Release Program Continuity requires source Vault Operations evidence."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_verifier import verify_unified_release_program_continuity_package

        runtime_report = verify_unified_release_program_continuity_package(
            archive_zip_path,
            strict=True,
            deep_restore=True,
            require_signed=True,
            require_current_vault_operations=True,
            signoff_binding_path=signoff_binding_path,
            vault_operations_archive_path=vault_operations_archive_path,
            vault_operations_verification_report_path=vault_operations_verification_report_path,
            vault_operations_signoff_binding_path=vault_operations_signoff_binding_path,
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
            "source_vault_operations_archive_sha256": (runtime_report.get("summary") or {}).get("source_vault_operations_archive_sha256"),
            "blockers": runtime_report.get("blockers", []),
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}

def _unified_release_program_continuity_kit_summary(
    *,
    required: bool,
    kit_zip_path: Path | str | None,
    kit_verification_report_path: Path | str | None,
    receiver_receipt_path: Path | str | None,
) -> DomainDocument:
    if kit_zip_path is None:
        return {"status": "missing", "message": "Unified Release Program Continuity Distribution Kit ZIP was not provided."}
    if required and kit_verification_report_path is None:
        return {"status": "failed", "message": "Unified Release Program Continuity Distribution Kit requires a verification report."}
    try:
        from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import verify_unified_release_program_continuity_distribution_package

        runtime_report = verify_unified_release_program_continuity_distribution_package(
            kit_zip_path,
            strict=True,
            deep=True,
            require_receiver_receipt=bool(receiver_receipt_path),
            receiver_receipt_path=receiver_receipt_path,
            kit_verification_report_path=kit_verification_report_path,
        )
        external_report: DomainDocument = {}
        if kit_verification_report_path is not None:
            external_report = read_json(Path(kit_verification_report_path))
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
            "receiver_receipt_required": bool(receiver_receipt_path),
            "blockers": runtime_report.get("blockers", []),
            "summary": runtime_report.get("summary", {}),
        }
    except Exception as exc:
        return {"status": "failed" if required else "missing", "error": str(exc)}
