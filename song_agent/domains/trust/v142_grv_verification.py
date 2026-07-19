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

key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global key
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"




def _verify_external_package_binding(
    checks: list[DomainDocument],
    prefix: str,
    ga_check: DomainDocument,
    zip_path: Path,
    verification_report: DomainDocument,
    runtime_report: DomainDocument,
    expected_package_type: str,
) -> None:
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
    _add_check(checks, f"{prefix}_verification_package_type", "passed" if verification_report.get("package_type") == expected_package_type else "failed", "blocking", "Verification package type is valid.")
    _add_check(checks, f"{prefix}_verification_integrity", "passed" if integrity_ok else "failed", "blocking", "Verification integrity hash matches.")
    _add_check(checks, f"{prefix}_verification_status", "passed" if verification_report.get("status") == "passed" and runtime_report.get("status") == "passed" else "failed", "blocking", "Verification is passed.", {"external_status": verification_report.get("status"), "current_status": runtime_report.get("status")})
    _add_check(
        checks,
        f"{prefix}_zip_binding",
        "passed"
        if external_fp.get("zip_sha256") == _sha256_file(zip_path)
        and int(external_fp.get("zip_size_bytes") or -1) == zip_path.stat().st_size == int(runtime_fp.get("zip_size_bytes") or -2)
        and external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        else "failed",
        "blocking",
        "Verification report matches ZIP size, hash, and manifest.",
    )
    _add_check(checks, f"{prefix}_ga_binding", "passed" if binding_ok else "failed", "blocking", "GA readiness check matches external verification.")

def _read_final_handoff_manifest(zip_path: Path) -> DomainDocument:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open("trust-operations-final-readiness-manifest.json") as file:
                return json.loads(file.read().decode("utf-8"))
    except Exception:
        return {}

def _verification_fingerprint(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
    }

def _verify_acceptance_report_from_store(report_path: Path, suite_id: str, report: DomainDocument) -> DomainDocument | None:
    if not suite_id:
        return None
    try:
        store_root = report_path.resolve().parents[1]
        if report_path.resolve().parent.name != suite_id:
            return None
        store = AcceptanceStore(store_root)
        return store.verify_report(suite_id, report)
    except Exception:
        return None

def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _add_check(checks: list[DomainDocument], check_id: str, status: str, severity: str, message: str, detail: DomainDocument | None = None) -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}})
