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
_verification_fingerprint = _make_deferred_global('_verification_fingerprint')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global _add_check, _sha256_file, _verification_fingerprint, key, value
    _add_check = namespace.get('_add_check', _add_check)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _verification_fingerprint = namespace.get('_verification_fingerprint', _verification_fingerprint)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"




def _verify_release_audio_baseline_governance_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    registry_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not registry_path:
        _add_check(checks, "ga_readiness_release_audio_baseline_registry_required", "failed", "blocking", "Release Audio Baseline Governance requirement needs a registry ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_baseline_verification_required", "failed", "blocking", "Release Audio Baseline Governance requirement needs a verification report.")
        return
    zip_path = Path(registry_path)
    try:
        verification_report = read_json(Path(verification_report_path))
        runtime_report = verify_release_audio_baseline_registry_package(zip_path, strict=True, require_active=True)
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_baseline_readable", "failed", "blocking", f"Release Audio Baseline Governance evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_baseline_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Baseline verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_baseline_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Baseline verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_baseline_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Baseline verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_baseline_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Baseline verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_baseline_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Baseline check matches external verification.")

def _verify_release_audio_regression_response_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    response_path: Path | str | None,
    verification_report_path: Path | str | None,
    regression_path: Path | str | None = None,
    regression_verification_report_path: Path | str | None = None,
    baseline_timeline_path: Path | str | None = None,
    baseline_timeline_verification_report_path: Path | str | None = None,
    baseline_certification_path: Path | str | None = None,
    baseline_certification_verification_report_path: Path | str | None = None,
    current_timeline_path: Path | str | None = None,
    current_timeline_verification_report_path: Path | str | None = None,
    current_certification_path: Path | str | None = None,
    current_certification_verification_report_path: Path | str | None = None,
) -> None:
    if not response_path:
        _add_check(checks, "ga_readiness_release_audio_regression_response_required", "failed", "blocking", "Release Audio Regression Response requirement needs a response ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_regression_response_verification_required", "failed", "blocking", "Release Audio Regression Response requirement needs a verification report.")
        return
    zip_path = Path(response_path)
    current_args = {
        "release_audio_regression_path": regression_path,
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
    missing_current = [key for key, value in current_args.items() if value is None]
    if missing_current:
        _add_check(
            checks,
            "ga_readiness_release_audio_regression_response_current_evidence_required",
            "failed",
            "blocking",
            "Release Audio Regression Response requirement needs current Release Audio Regression evidence.",
            {"missing": missing_current},
        )
        return
    try:
        verification_report = read_json(Path(verification_report_path))
        runtime_report = verify_release_audio_regression_response_package(
            zip_path,
            strict=True,
            require_closed=True,
            require_signed=True,
            require_regression_current=True,
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
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_regression_response_readable", "failed", "blocking", f"Release Audio Regression Response evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_regression_response_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Regression Response verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_regression_response_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Regression Response verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_regression_response_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Regression Response verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_regression_response_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Regression Response verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_regression_response_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Regression Response check matches external verification.")

def _verify_release_audio_quality_observatory_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    observatory_path: Path | str | None,
    verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
    *,
    require_no_critical_audio_quality_risk: bool,
) -> None:
    if not observatory_path:
        _add_check(checks, "ga_readiness_release_audio_quality_observatory_required", "failed", "blocking", "Release Audio Quality Observatory requirement needs an external Observatory ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_quality_observatory_verification_required", "failed", "blocking", "Release Audio Quality Observatory requirement needs a verification report.")
        return
    if not evidence_root:
        _add_check(checks, "ga_readiness_release_audio_quality_observatory_evidence_root_required", "failed", "blocking", "Release Audio Quality Observatory requirement needs an evidence root.")
        return
    zip_path = Path(observatory_path)
    try:
        verification_report = read_json(Path(verification_report_path))
        runtime_report = verify_release_audio_quality_observatory_package(
            zip_path,
            strict=True,
            require_current_evidence=True,
            evidence_root=evidence_root,
            require_no_critical_risk=require_no_critical_audio_quality_risk,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_quality_observatory_readable", "failed", "blocking", f"Release Audio Quality Observatory evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_quality_observatory_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Quality Observatory verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_quality_observatory_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Quality Observatory verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_quality_observatory_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Quality Observatory verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_quality_observatory_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Quality Observatory verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_quality_observatory_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Quality Observatory check matches external verification.")

def _verify_release_audio_quality_action_queue_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    queue_path: Path | str | None,
    verification_report_path: Path | str | None,
    observatory_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> None:
    if not queue_path:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_required", "failed", "blocking", "Release Audio Quality Action Queue requirement needs an external Action Queue ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_verification_required", "failed", "blocking", "Release Audio Quality Action Queue requirement needs a verification report.")
        return
    if not observatory_path or not observatory_verification_report_path or not evidence_root:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_observatory_required", "failed", "blocking", "Release Audio Quality Action Queue requirement needs current Observatory ZIP, verification report, and evidence root.")
        return
    zip_path = Path(queue_path)
    try:
        verification_report = read_json(Path(verification_report_path))
        runtime_report = verify_release_audio_quality_action_queue_package(
            zip_path,
            strict=True,
            require_current_observatory=True,
            observatory_zip_path=observatory_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
            require_no_blocking=True,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_readable", "failed", "blocking", f"Release Audio Quality Action Queue evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Quality Action Queue verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Quality Action Queue verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Quality Action Queue verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Quality Action Queue verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Quality Action Queue check matches external verification.")

def _verify_release_audio_quality_action_queue_signoff_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    queue_path: Path | str | None,
    queue_verification_report_path: Path | str | None,
    observatory_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_required", "failed", "blocking", "Release Audio Quality Action Queue signoff requirement needs an external signoff archive ZIP.")
        return
    if not archive_verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_verification_required", "failed", "blocking", "Release Audio Quality Action Queue signoff requirement needs a verification report.")
        return
    if not queue_path or not queue_verification_report_path or not observatory_path or not observatory_verification_report_path or not evidence_root:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_queue_required", "failed", "blocking", "Release Audio Quality Action Queue signoff requirement needs current Action Queue and Observatory evidence.")
        return
    zip_path = Path(archive_path)
    try:
        verification_report = read_json(Path(archive_verification_report_path))
        runtime_report = verify_release_audio_quality_action_queue_signoff_archive_package(
            zip_path,
            strict=True,
            require_current_queue=True,
            require_signed=True,
            queue_zip_path=queue_path,
            queue_verification_report_path=queue_verification_report_path,
            observatory_zip_path=observatory_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
            require_no_unresolved_manual=True,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_readable", "failed", "blocking", f"Release Audio Quality Action Queue signoff evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Quality Action Queue signoff verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Quality Action Queue signoff verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Quality Action Queue signoff verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Quality Action Queue signoff verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_quality_action_queue_signoff_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Quality Action Queue signoff check matches external verification.")

def _verify_release_audio_command_center_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    certification_path: Path | str | None,
    certification_verification_report_path: Path | str | None,
    timeline_path: Path | str | None,
    timeline_verification_report_path: Path | str | None,
    regression_path: Path | str | None,
    regression_verification_report_path: Path | str | None,
    baseline_registry_path: Path | str | None,
    baseline_registry_verification_report_path: Path | str | None,
    regression_response_path: Path | str | None,
    regression_response_verification_report_path: Path | str | None,
    observatory_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    action_queue_path: Path | str | None,
    action_queue_verification_report_path: Path | str | None,
    action_queue_signoff_archive_path: Path | str | None,
    action_queue_signoff_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> None:
    if not command_center_path:
        _add_check(checks, "ga_readiness_release_audio_command_center_required", "failed", "blocking", "Release Audio Command Center requirement needs an external Command Center ZIP.")
        return
    if not command_center_verification_report_path:
        _add_check(checks, "ga_readiness_release_audio_command_center_verification_required", "failed", "blocking", "Release Audio Command Center requirement needs a verification report.")
        return
    zip_path = Path(command_center_path)
    try:
        verification_report = read_json(Path(command_center_verification_report_path))
        runtime_report = verify_release_audio_command_center_package(
            zip_path,
            strict=True,
            require_ready=True,
            certification_zip_path=certification_path,
            certification_verification_report_path=certification_verification_report_path,
            timeline_zip_path=timeline_path,
            timeline_verification_report_path=timeline_verification_report_path,
            regression_zip_path=regression_path,
            regression_verification_report_path=regression_verification_report_path,
            baseline_registry_zip_path=baseline_registry_path,
            baseline_registry_verification_report_path=baseline_registry_verification_report_path,
            regression_response_zip_path=regression_response_path,
            regression_response_verification_report_path=regression_response_verification_report_path,
            observatory_zip_path=observatory_path,
            observatory_verification_report_path=observatory_verification_report_path,
            action_queue_zip_path=action_queue_path,
            action_queue_verification_report_path=action_queue_verification_report_path,
            action_queue_signoff_archive_path=action_queue_signoff_archive_path,
            action_queue_signoff_verification_report_path=action_queue_signoff_verification_report_path,
            evidence_root=evidence_root,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_command_center_readable", "failed", "blocking", f"Release Audio Command Center evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_release_audio_command_center_verification_package_type", "passed" if verification_report.get("package_type") == RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Release Audio Command Center verification package type is valid.")
    _add_check(checks, "ga_readiness_release_audio_command_center_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Release Audio Command Center verification integrity hash matches.")
    _add_check(checks, "ga_readiness_release_audio_command_center_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Release Audio Command Center verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_release_audio_command_center_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Release Audio Command Center verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_release_audio_command_center_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Release Audio Command Center check matches external verification.")

def _verify_unified_command_center_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    release_path: Path | str | None,
    release_verification_report_path: Path | str | None,
    release_audio_command_center_path: Path | str | None,
    release_audio_command_center_verification_report_path: Path | str | None,
    distribution_paths: list[Path | str] | tuple[Path | str, ...] | None,
    distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    submission_paths: list[Path | str] | tuple[Path | str, ...] | None,
    submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    release_operations_path: Path | str | None,
    release_operations_verification_report_path: Path | str | None,
    trust_operations_hub_path: Path | str | None,
    trust_operations_hub_verification_report_path: Path | str | None,
    public_trust_center_path: Path | str | None,
    public_trust_center_verification_report_path: Path | str | None,
    maintenance_backup_path: Path | str | None,
    maintenance_backup_verification_report_path: Path | str | None,
) -> None:
    if not command_center_path:
        _add_check(checks, "ga_readiness_unified_command_center_required", "failed", "blocking", "Unified Command Center requirement needs an external Unified Command Center ZIP.")
        return
    if not command_center_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_verification_required", "failed", "blocking", "Unified Command Center requirement needs a verification report.")
        return
    zip_path = Path(command_center_path)
    try:
        from song_agent.domains.program.unified_command_center_verifier import UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_package

        verification_report = read_json(Path(command_center_verification_report_path))
        runtime_report = verify_unified_command_center_package(
            zip_path,
            strict=True,
            require_ready=True,
            release_zip_path=release_path,
            release_verification_report_path=release_verification_report_path,
            release_audio_command_center_zip_path=release_audio_command_center_path,
            release_audio_command_center_verification_report_path=release_audio_command_center_verification_report_path,
            distribution_zip_paths=list(distribution_paths or []),
            distribution_verification_report_paths=list(distribution_verification_report_paths or []),
            submission_zip_paths=list(submission_paths or []),
            submission_verification_report_paths=list(submission_verification_report_paths or []),
            release_operations_zip_path=release_operations_path,
            release_operations_verification_report_path=release_operations_verification_report_path,
            trust_operations_hub_zip_path=trust_operations_hub_path,
            trust_operations_hub_verification_report_path=trust_operations_hub_verification_report_path,
            public_trust_center_zip_path=public_trust_center_path,
            public_trust_center_verification_report_path=public_trust_center_verification_report_path,
            maintenance_backup_zip_path=maintenance_backup_path,
            maintenance_backup_verification_report_path=maintenance_backup_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_readable", "failed", "blocking", f"Unified Command Center evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = _as_document(ga_check.get("detail"))
    external_fp = _verification_fingerprint(verification_report)
    runtime_fp = _verification_fingerprint(runtime_report)
    binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("zip_sha256") == external_fp.get("zip_sha256")
        and detail.get("manifest_hash") == external_fp.get("manifest_hash")
        and detail.get("verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(checks, "ga_readiness_unified_command_center_verification_package_type", "passed" if verification_report.get("package_type") == UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE else "failed", "blocking", "Unified Command Center verification package type is valid.")
    _add_check(checks, "ga_readiness_unified_command_center_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Unified Command Center verification integrity hash matches.")
    _add_check(checks, "ga_readiness_unified_command_center_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Unified Command Center verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(checks, "ga_readiness_unified_command_center_zip_binding", "passed" if external_fp.get("zip_sha256") == _sha256_file(zip_path) and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash") else "failed", "blocking", "Unified Command Center verification report matches ZIP and manifest.")
    _add_check(checks, "ga_readiness_unified_command_center_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness Unified Command Center check matches external verification.")
