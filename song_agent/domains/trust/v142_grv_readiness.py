# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path
import json as json
import re as re
import hashlib as hashlib
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE as GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION as GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok as ga_readiness_integrity_ok
from song_agent.application.policy_compatibility import canonical_ga_policy_id as canonical_ga_policy_id, evaluate_check_policy as evaluate_check_policy, normalized_legacy_require_payload as normalized_legacy_require_payload
from song_agent.domains.quality.audio_campaign_archive_verifier import verify_audio_campaign_archive_package as verify_audio_campaign_archive_package
from song_agent.domains.quality.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package as verify_audio_campaign_remediation_package
from song_agent.domains.quality.release_audio_certification_verifier import RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE, verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE, verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.quality.release_audio_regression_verifier import RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE, verify_release_audio_regression_package as verify_release_audio_regression_package
from song_agent.domains.quality.release_audio_baseline_governance_verifier import RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE, verify_release_audio_baseline_registry_package as verify_release_audio_baseline_registry_package
from song_agent.domains.quality.release_audio_regression_response_verifier import RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE, verify_release_audio_regression_response_package as verify_release_audio_regression_response_package
from song_agent.domains.quality.release_audio_quality_observatory_verifier import RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_observatory_package as verify_release_audio_quality_observatory_package
from song_agent.domains.quality.release_audio_quality_actions_verifier import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_action_queue_package as verify_release_audio_quality_action_queue_package
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_action_queue_signoff_archive_package as verify_release_audio_quality_action_queue_signoff_archive_package
from song_agent.domains.quality.release_audio_command_center_verifier import RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_release_audio_command_center_package as verify_release_audio_command_center_package
from song_agent.domains.quality.music_acceptance import AcceptanceStore as AcceptanceStore
from song_agent.domains.quality.music_acceptance import stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.delivery.releases import stable_hash as release_stable_hash
from song_agent.domains.trust.trust_operations_final_readiness_verifier import TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_trust_operations_final_handoff_package as verify_trust_operations_final_handoff_package

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

_add_check = _make_deferred_global('_add_check')
_sha256_file = _make_deferred_global('_sha256_file')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global _add_check, _sha256_file, key, value
    _add_check = namespace.get('_add_check', _add_check)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"




def _verify_audio_campaign_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_audio_campaign_archive_required", "failed", "blocking", "Audio Campaign requirement needs an external Audio Campaign Archive ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_audio_campaign_verification_required", "failed", "blocking", "Audio Campaign requirement needs an external Audio Campaign Archive verification report.")
        return
    zip_path = Path(archive_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_audio_campaign_verification_readable", "failed", "blocking", f"Audio Campaign Archive verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_audio_campaign_verification_readable", "passed", "info", "Audio Campaign Archive verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_audio_campaign_archive_package(zip_path, strict=True, require_signed=True, require_verification_passed=True)
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    current_summary = _as_document(current_verification.get("summary"))
    report_summary = _as_document(verification_report.get("summary"))
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_package_type",
        "passed" if verification_report.get("package_type") == "audio_campaign_archive_verification" else "failed",
        "blocking",
        "Audio Campaign Archive verification package type is valid." if verification_report.get("package_type") == "audio_campaign_archive_verification" else "Audio Campaign Archive verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Audio Campaign Archive verification report integrity hash matches." if report_integrity_ok else "Audio Campaign Archive verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_status",
        "passed" if verification_report.get("status") == "passed" else "failed",
        "blocking",
        "Audio Campaign Archive verification report is passed." if verification_report.get("status") == "passed" else "Audio Campaign Archive verification report is not passed.",
        {"status": verification_report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_archive_self_verification",
        "passed" if current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Audio Campaign Archive ZIP self-verification is passed." if current_verification.get("status") == "passed" else "Audio Campaign Archive ZIP self-verification failed.",
        {"status": current_verification.get("status"), "blockers": current_verification.get("blockers", [])},
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_zip_binding",
        "passed" if report_summary.get("zip_sha256") == current_summary.get("zip_sha256") and report_summary.get("manifest_hash") == current_summary.get("manifest_hash") else "failed",
        "blocking",
        "Audio Campaign Archive verification report matches the ZIP and manifest." if report_summary.get("zip_sha256") == current_summary.get("zip_sha256") and report_summary.get("manifest_hash") == current_summary.get("manifest_hash") else "Audio Campaign Archive verification report does not match the ZIP and manifest.",
        {"zip_sha256": current_summary.get("zip_sha256"), "manifest_hash": current_summary.get("manifest_hash")},
    )
    detail = _as_document(ga_check.get("detail"))
    gate = _as_document(detail.get("gate"))
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and gate.get("archive_zip_sha256") == current_summary.get("zip_sha256")
        and gate.get("archive_verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Audio Campaign check matches the external archive verification." if ga_binding_ok else "GA readiness Audio Campaign check does not match the external archive verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": current_summary.get("zip_sha256"), "ga_zip_sha256": gate.get("archive_zip_sha256")},
    )

def _verify_audio_campaign_remediation_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    remediation_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not remediation_path:
        _add_check(checks, "ga_readiness_audio_campaign_remediation_package_required", "failed", "blocking", "Audio Campaign remediation requirement needs an external remediation ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_audio_campaign_remediation_verification_required", "failed", "blocking", "Audio Campaign remediation requirement needs an external remediation verification report.")
        return
    zip_path = Path(remediation_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_audio_campaign_remediation_verification_readable", "failed", "blocking", f"Audio Campaign remediation verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_audio_campaign_remediation_verification_readable", "passed", "info", "Audio Campaign remediation verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_audio_campaign_remediation_package(zip_path, strict=True, require_passed=True)
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    _add_check(
        checks,
        "ga_readiness_audio_campaign_remediation_verification_package_type",
        "passed" if verification_report.get("package_type") == "audio_campaign_remediation_verification" else "failed",
        "blocking",
        "Audio Campaign remediation verification package type is valid." if verification_report.get("package_type") == "audio_campaign_remediation_verification" else "Audio Campaign remediation verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_remediation_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Audio Campaign remediation verification report integrity hash matches." if report_integrity_ok else "Audio Campaign remediation verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_remediation_verification_status",
        "passed" if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Audio Campaign remediation verification is passed." if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "Audio Campaign remediation verification is not passed.",
        {"external_status": verification_report.get("status"), "current_status": current_verification.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_remediation_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Audio Campaign remediation verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Audio Campaign remediation verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash")},
    )
    detail = _as_document(ga_check.get("detail"))
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_remediation_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Audio Campaign remediation check matches the external remediation verification." if ga_binding_ok else "GA readiness Audio Campaign remediation check does not match the external remediation verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )

def _verify_release_audio_certification_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    certification_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not certification_path:
        _add_check(checks, "ga_readiness_release_audio_certification_package_required", "failed", "blocking", "Release Audio Certification requirement needs an external certification ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_certification_verification_required", "failed", "blocking", "Release Audio Certification requirement needs an external certification verification report.")
        return
    zip_path = Path(certification_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_certification_verification_readable", "failed", "blocking", f"Release Audio Certification verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_release_audio_certification_verification_readable", "passed", "info", "Release Audio Certification verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_release_audio_certification_package(
            zip_path,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_real_audio=True,
            require_manual_review=True,
            require_remediation_when_needed=True,
        )
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_verification_package_type",
        "passed" if verification_report.get("package_type") == RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE else "failed",
        "blocking",
        "Release Audio Certification verification package type is valid." if verification_report.get("package_type") == RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE else "Release Audio Certification verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Release Audio Certification verification report integrity hash matches." if report_integrity_ok else "Release Audio Certification verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_verification_status",
        "passed" if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Release Audio Certification verification is passed." if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "Release Audio Certification verification is not passed.",
        {"external_status": verification_report.get("status"), "current_status": current_verification.get("status")},
    )
    current_summary = _as_document(current_verification.get("summary"))
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Certification verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Certification verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "track_count": current_summary.get("track_count")},
    )
    detail = _as_document(ga_check.get("detail"))
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Release Audio Certification check matches the external certification verification." if ga_binding_ok else "GA readiness Release Audio Certification check does not match the external certification verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )

def _verify_release_audio_timeline_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    timeline_path: Path | str | None,
    verification_report_path: Path | str | None,
    certification_path: Path | str | None,
    certification_verification_report_path: Path | str | None,
) -> None:
    if not timeline_path:
        _add_check(checks, "ga_readiness_release_audio_timeline_package_required", "failed", "blocking", "Release Audio Timeline requirement needs an external timeline ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_timeline_verification_required", "failed", "blocking", "Release Audio Timeline requirement needs an external timeline verification report.")
        return
    zip_path = Path(timeline_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_timeline_verification_readable", "failed", "blocking", f"Release Audio Timeline verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_release_audio_timeline_verification_readable", "passed", "info", "Release Audio Timeline verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_release_audio_timeline_package(
            zip_path,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_real_audio=True,
            require_manual_review=True,
            require_current_certification=True,
            release_audio_certification_path=certification_path,
            release_audio_certification_verification_report_path=certification_verification_report_path,
        )
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_verification_package_type",
        "passed" if verification_report.get("package_type") == RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE else "failed",
        "blocking",
        "Release Audio Timeline verification package type is valid." if verification_report.get("package_type") == RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE else "Release Audio Timeline verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Release Audio Timeline verification report integrity hash matches." if report_integrity_ok else "Release Audio Timeline verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_verification_status",
        "passed" if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Release Audio Timeline verification is passed." if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "Release Audio Timeline verification is not passed.",
        {"external_status": verification_report.get("status"), "current_status": current_verification.get("status")},
    )
    current_summary = _as_document(current_verification.get("summary"))
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Timeline verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Timeline verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "track_count": current_summary.get("track_count")},
    )
    detail = _as_document(ga_check.get("detail"))
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Release Audio Timeline check matches the external timeline verification." if ga_binding_ok else "GA readiness Release Audio Timeline check does not match the external timeline verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )

def _verify_release_audio_regression_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    regression_path: Path | str | None,
    verification_report_path: Path | str | None,
    baseline_timeline_path: Path | str | None,
    baseline_timeline_verification_report_path: Path | str | None,
    baseline_certification_path: Path | str | None,
    baseline_certification_verification_report_path: Path | str | None,
    current_timeline_path: Path | str | None,
    current_timeline_verification_report_path: Path | str | None,
    current_certification_path: Path | str | None,
    current_certification_verification_report_path: Path | str | None,
) -> None:
    if not regression_path:
        _add_check(checks, "ga_readiness_release_audio_regression_package_required", "failed", "blocking", "Release Audio Regression requirement needs an external regression ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_regression_verification_required", "failed", "blocking", "Release Audio Regression requirement needs an external regression verification report.")
        return
    zip_path = Path(regression_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_regression_verification_readable", "failed", "blocking", f"Release Audio Regression verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_release_audio_regression_verification_readable", "passed", "info", "Release Audio Regression verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_release_audio_regression_package(
            zip_path,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_current=True,
            require_baseline_current=True,
            baseline_timeline_path=baseline_timeline_path,
            baseline_timeline_verification_report_path=baseline_timeline_verification_report_path,
            baseline_certification_path=baseline_certification_path,
            baseline_certification_verification_report_path=baseline_certification_verification_report_path,
            current_timeline_path=current_timeline_path,
            current_timeline_verification_report_path=current_timeline_verification_report_path,
            current_certification_path=current_certification_path,
            current_certification_verification_report_path=current_certification_verification_report_path,
        )
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_verification_package_type",
        "passed" if verification_report.get("package_type") == RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE else "failed",
        "blocking",
        "Release Audio Regression verification package type is valid." if verification_report.get("package_type") == RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE else "Release Audio Regression verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Release Audio Regression verification report integrity hash matches." if report_integrity_ok else "Release Audio Regression verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_verification_status",
        "passed" if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Release Audio Regression verification is passed." if verification_report.get("status") == "passed" and current_verification.get("status") == "passed" else "Release Audio Regression verification is not passed.",
        {"external_status": verification_report.get("status"), "current_status": current_verification.get("status")},
    )
    current_summary = _as_document(current_verification.get("summary"))
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Regression verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Regression verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "release_id": current_summary.get("release_id"), "baseline_release_id": current_summary.get("baseline_release_id")},
    )
    detail = _as_document(ga_check.get("detail"))
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Release Audio Regression check matches the external regression verification." if ga_binding_ok else "GA readiness Release Audio Regression check does not match the external regression verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )
