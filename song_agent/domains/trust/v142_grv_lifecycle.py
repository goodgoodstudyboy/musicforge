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
_verify_external_package_binding = _make_deferred_global('_verify_external_package_binding')

def bind_globals(namespace: dict[str, object]) -> None:
    global _add_check, _verify_external_package_binding
    _add_check = namespace.get('_add_check', _add_check)
    _verify_external_package_binding = namespace.get('_verify_external_package_binding', _verify_external_package_binding)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"




def _verify_unified_command_center_archive_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_unified_command_center_archive_required", "failed", "blocking", "Unified Command Center Archive requirement needs an archive ZIP.")
        return
    if not archive_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_archive_verification_required", "failed", "blocking", "Unified Command Center Archive requirement needs a verification report.")
        return
    zip_path = Path(archive_path)
    try:
        from song_agent.domains.program.unified_command_center_archive_verifier import UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_archive_package

        verification_report = read_json(Path(archive_verification_report_path))
        runtime_report = verify_unified_command_center_archive_package(
            zip_path,
            strict=True,
            require_signed=True,
            require_current_ucc=bool(command_center_path and command_center_verification_report_path),
            command_center_zip_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_archive_readable", "failed", "blocking", f"Unified Command Center Archive evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_archive",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_command_center_handoff_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    handoff_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
) -> None:
    if not handoff_path:
        _add_check(checks, "ga_readiness_unified_command_center_handoff_required", "failed", "blocking", "Unified Command Center Handoff requirement needs a handoff ZIP.")
        return
    if not handoff_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_handoff_verification_required", "failed", "blocking", "Unified Command Center Handoff requirement needs a verification report.")
        return
    zip_path = Path(handoff_path)
    try:
        from song_agent.domains.program.unified_command_center_handoff_verifier import UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_handoff_package

        verification_report = read_json(Path(handoff_verification_report_path))
        runtime_report = verify_unified_command_center_handoff_package(
            zip_path,
            strict=True,
            require_archive=bool(archive_path and archive_verification_report_path),
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_handoff_readable", "failed", "blocking", f"Unified Command Center Handoff evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_handoff",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_command_center_continuous_review_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    review_path: Path | str | None,
    review_verification_report_path: Path | str | None,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
) -> None:
    if not review_path:
        _add_check(checks, "ga_readiness_unified_command_center_continuous_review_required", "failed", "blocking", "Unified Command Center Continuous Review requirement needs a review ZIP.")
        return
    if not review_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_continuous_review_verification_required", "failed", "blocking", "Unified Command Center Continuous Review requirement needs a verification report.")
        return
    zip_path = Path(review_path)
    try:
        from song_agent.domains.program.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package

        verification_report = read_json(Path(review_verification_report_path))
        runtime_report = verify_unified_command_center_continuous_review_package(
            zip_path,
            strict=True,
            require_clear=True,
            require_recovery_drill=True,
            require_current_review=True,
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_path,
            handoff_verification_report_path=handoff_verification_report_path,
            command_center_zip_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_continuous_review_readable", "failed", "blocking", f"Unified Command Center Continuous Review evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_continuous_review",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_command_center_drift_response_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    response_path: Path | str | None,
    response_verification_report_path: Path | str | None,
    source_review_path: Path | str | None,
    source_review_verification_report_path: Path | str | None,
    recheck_review_path: Path | str | None,
    recheck_review_verification_report_path: Path | str | None,
    change_request_binding_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
) -> None:
    if not response_path:
        _add_check(checks, "ga_readiness_unified_command_center_drift_response_required", "failed", "blocking", "Unified Command Center Drift Response requirement needs a response ZIP.")
        return
    if not response_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_drift_response_verification_required", "failed", "blocking", "Unified Command Center Drift Response requirement needs a verification report.")
        return
    if not change_request_binding_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_drift_response_cr_proof_required", "failed", "blocking", "Unified Command Center Drift Response requirement needs an external Change Request binding report.")
        return
    zip_path = Path(response_path)
    try:
        from song_agent.domains.program.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package

        verification_report = read_json(Path(response_verification_report_path))
        runtime_report = verify_unified_command_center_drift_response_package(
            zip_path,
            strict=True,
            require_closed=True,
            require_recheck_clear=True,
            require_current_review=True,
            source_review_zip_path=source_review_path,
            source_review_verification_report_path=source_review_verification_report_path,
            recheck_review_zip_path=recheck_review_path,
            recheck_review_verification_report_path=recheck_review_verification_report_path,
            change_request_binding_report_path=change_request_binding_report_path,
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_path,
            handoff_verification_report_path=handoff_verification_report_path,
            command_center_zip_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_drift_response_readable", "failed", "blocking", f"Unified Command Center Drift Response evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_drift_response",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_command_center_evidence_review_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    review_path: Path | str | None,
    review_verification_report_path: Path | str | None,
    require_accepted: bool,
    acceptance_path: Path | str | None,
    acceptance_verification_report_path: Path | str | None,
    acceptance_response_verification_report_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    continuous_review_path: Path | str | None,
    continuous_review_verification_report_path: Path | str | None,
    drift_response_path: Path | str | None,
    drift_response_verification_report_path: Path | str | None,
    source_review_path: Path | str | None,
    source_review_verification_report_path: Path | str | None,
    recheck_review_path: Path | str | None,
    recheck_review_verification_report_path: Path | str | None,
    drift_change_request_binding_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    release_check_report_path: Path | str | None,
) -> None:
    if not review_path:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_required", "failed", "blocking", "Unified Command Center Evidence Review requirement needs a review ZIP.")
        return
    if not review_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_verification_required", "failed", "blocking", "Unified Command Center Evidence Review requirement needs a verification report.")
        return
    zip_path = Path(review_path)
    try:
        from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package

        verification_report = read_json(Path(review_verification_report_path))
        runtime_report = verify_unified_command_center_evidence_review_package(
            zip_path,
            strict=True,
            require_replay_passed=True,
            ucc_zip_path=command_center_path,
            ucc_verification_report_path=command_center_verification_report_path,
            archive_zip_path=archive_path,
            archive_verification_report_path=archive_verification_report_path,
            handoff_zip_path=handoff_path,
            handoff_verification_report_path=handoff_verification_report_path,
            continuous_review_zip_path=continuous_review_path,
            continuous_review_verification_report_path=continuous_review_verification_report_path,
            drift_response_zip_path=drift_response_path,
            drift_response_verification_report_path=drift_response_verification_report_path,
            drift_change_request_binding_report_path=drift_change_request_binding_report_path,
            source_review_zip_path=source_review_path,
            source_review_verification_report_path=source_review_verification_report_path,
            recheck_review_zip_path=recheck_review_path,
            recheck_review_verification_report_path=recheck_review_verification_report_path,
            signoff_binding_path=signoff_binding_path,
            release_check_report_path=release_check_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_readable", "failed", "blocking", f"Unified Command Center Evidence Review evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_evidence_review",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE,
    )
    if not require_accepted:
        return
    if not acceptance_path:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_acceptance_required", "failed", "blocking", "Unified Command Center Evidence Review accepted evidence requirement needs an acceptance ZIP.")
        return
    if not acceptance_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_acceptance_verification_required", "failed", "blocking", "Unified Command Center Evidence Review accepted evidence requirement needs a verification report.")
        return
    if not acceptance_response_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_acceptance_response_verification_required", "failed", "blocking", "Unified Command Center Evidence Review accepted evidence requirement needs the original response verification summary.")
        return
    acceptance_zip_path = Path(acceptance_path)
    try:
        acceptance_verification_report = read_json(Path(acceptance_verification_report_path))
        acceptance_runtime_report = verify_unified_command_center_evidence_review_acceptance_package(
            acceptance_zip_path,
            strict=True,
            require_accepted=True,
            review_pack_path=review_path,
            review_pack_verification_report_path=review_verification_report_path,
            response_verification_report_path=acceptance_response_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_evidence_review_acceptance_readable", "failed", "blocking", f"Unified Command Center Evidence Review accepted evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_evidence_review_acceptance",
        {"status": "passed", "detail": {"zip_sha256": acceptance_verification_report.get("zip_sha256"), "manifest_hash": acceptance_verification_report.get("manifest_hash"), "verification_hash": acceptance_verification_report.get("integrity_hash")}},
        acceptance_zip_path,
        acceptance_verification_report,
        acceptance_runtime_report,
        UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_command_center_reviewer_decision_board_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    board_path: Path | str | None,
    board_verification_report_path: Path | str | None,
    require_signed: bool,
    require_quorum: bool,
    evidence_review_path: Path | str | None,
    evidence_review_verification_report_path: Path | str | None,
    accepted_evidence_paths: list[Path | str] | tuple[Path | str, ...] | None,
    accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
    accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None,
) -> None:
    if not board_path:
        _add_check(checks, "ga_readiness_unified_command_center_reviewer_decision_board_required", "failed", "blocking", "Unified Command Center Reviewer Decision Board requirement needs a Board archive ZIP.")
        return
    if not board_verification_report_path:
        _add_check(checks, "ga_readiness_unified_command_center_reviewer_decision_board_verification_required", "failed", "blocking", "Unified Command Center Reviewer Decision Board requirement needs a verification report.")
        return
    zip_path = Path(board_path)
    try:
        from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import verify_unified_command_center_reviewer_decision_board_package

        verification_report = read_json(Path(board_verification_report_path))
        runtime_report = verify_unified_command_center_reviewer_decision_board_package(
            zip_path,
            strict=True,
            require_signed=require_signed,
            require_quorum=require_quorum,
            evidence_review_path=evidence_review_path,
            evidence_review_verification_report_path=evidence_review_verification_report_path,
            accepted_evidence_paths=_as_list(accepted_evidence_paths or []),
            accepted_evidence_verification_report_paths=_as_list(accepted_evidence_verification_report_paths or []),
            accepted_evidence_response_verification_report_paths=_as_list(accepted_evidence_response_verification_report_paths or []),
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_command_center_reviewer_decision_board_readable", "failed", "blocking", f"Unified Command Center Reviewer Decision Board evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_command_center_reviewer_decision_board",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_handoff_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    handoff_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
    handoff_signoff_binding_path: Path | str | None,
) -> None:
    if not handoff_path:
        _add_check(checks, "ga_readiness_unified_release_program_handoff_required", "failed", "blocking", "Unified Release Program Handoff requirement needs a Handoff archive ZIP.")
        return
    if not handoff_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_handoff_verification_required", "failed", "blocking", "Unified Release Program Handoff requirement needs a verification report.")
        return
    zip_path = Path(handoff_path)
    try:
        from song_agent.domains.program.unified_release_program_handoff_verifier import UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_handoff_package

        verification_report = read_json(Path(handoff_verification_report_path))
        runtime_report = verify_unified_release_program_handoff_package(
            zip_path,
            strict=True,
            require_current=True,
            require_accepted=True,
            require_signed=True,
            external_evidence_manifest_path=external_evidence_manifest_path,
            handoff_signoff_binding_path=handoff_signoff_binding_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_handoff_readable", "failed", "blocking", f"Unified Release Program Handoff evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_handoff",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_vault_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    vault_path: Path | str | None,
    vault_verification_report_path: Path | str | None,
    vault_anchor_path: Path | str | None,
) -> None:
    if not vault_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_required", "failed", "blocking", "Unified Release Program Evidence Vault requirement needs a Vault ZIP.")
        return
    if not vault_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_verification_required", "failed", "blocking", "Unified Release Program Evidence Vault requirement needs a verification report.")
        return
    if not vault_anchor_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_anchor_required", "failed", "blocking", "Unified Release Program Evidence Vault requirement needs an external anchor.")
        return
    zip_path = Path(vault_path)
    try:
        from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package

        verification_report = read_json(Path(vault_verification_report_path))
        runtime_report = verify_unified_release_program_vault_package(
            zip_path,
            strict=True,
            deep=True,
            require_anchor=True,
            vault_anchor_path=vault_anchor_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_vault_readable", "failed", "blocking", f"Unified Release Program Evidence Vault evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_vault",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    )
