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




def _verify_unified_release_program_vault_operations_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_operations_required", "failed", "blocking", "Unified Release Program Vault Operations requirement needs an archive ZIP.")
        return
    if not archive_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_operations_verification_required", "failed", "blocking", "Unified Release Program Vault Operations requirement needs a verification report.")
        return
    if not signoff_binding_path:
        _add_check(checks, "ga_readiness_unified_release_program_vault_operations_binding_required", "failed", "blocking", "Unified Release Program Vault Operations requirement needs a signoff binding.")
        return
    zip_path = Path(archive_path)
    try:
        from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package

        verification_report = read_json(Path(archive_verification_report_path))
        runtime_report = verify_unified_release_program_vault_operations_package(
            zip_path,
            strict=True,
            deep=True,
            require_signed=True,
            require_current_vault=True,
            signoff_binding_path=signoff_binding_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_vault_operations_readable", "failed", "blocking", f"Unified Release Program Vault Operations evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_vault_operations",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    vault_operations_path: Path | str | None,
    vault_operations_verification_report_path: Path | str | None,
    vault_operations_signoff_binding_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_required", "failed", "blocking", "Unified Release Program Continuity requirement needs an archive ZIP.")
        return
    if not archive_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_verification_required", "failed", "blocking", "Unified Release Program Continuity requirement needs a verification report.")
        return
    if not signoff_binding_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_binding_required", "failed", "blocking", "Unified Release Program Continuity requirement needs a signoff binding.")
        return
    if not vault_operations_path or not vault_operations_verification_report_path or not vault_operations_signoff_binding_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_source_required", "failed", "blocking", "Unified Release Program Continuity requirement needs source Vault Operations evidence.")
        return
    zip_path = Path(archive_path)
    try:
        from song_agent.domains.program.unified_release_program_continuity_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_package

        verification_report = read_json(Path(archive_verification_report_path))
        runtime_report = verify_unified_release_program_continuity_package(
            zip_path,
            strict=True,
            deep_restore=True,
            require_signed=True,
            require_current_vault_operations=True,
            signoff_binding_path=signoff_binding_path,
            vault_operations_archive_path=vault_operations_path,
            vault_operations_verification_report_path=vault_operations_verification_report_path,
            vault_operations_signoff_binding_path=vault_operations_signoff_binding_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_readable", "failed", "blocking", f"Unified Release Program Continuity evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_kit_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    kit_path: Path | str | None,
    kit_verification_report_path: Path | str | None,
    receiver_receipt_path: Path | str | None,
) -> None:
    if not kit_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_kit_required", "failed", "blocking", "Unified Release Program Continuity Distribution Kit requirement needs a kit ZIP.")
        return
    if not kit_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_kit_verification_required", "failed", "blocking", "Unified Release Program Continuity Distribution Kit requirement needs a verification report.")
        return
    zip_path = Path(kit_path)
    try:
        from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_distribution_package

        verification_report = read_json(Path(kit_verification_report_path))
        runtime_report = verify_unified_release_program_continuity_distribution_package(
            zip_path,
            strict=True,
            deep=True,
            require_receiver_receipt=bool(receiver_receipt_path),
            receiver_receipt_path=receiver_receipt_path,
            kit_verification_report_path=kit_verification_report_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_kit_readable", "failed", "blocking", f"Unified Release Program Continuity Distribution Kit evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_kit",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_acceptance_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    kit_path: Path | str | None,
    kit_verification_report_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_acceptance_required", "failed", "blocking", "Unified Release Program Continuity Acceptance requirement needs an archive ZIP.")
        return
    if not archive_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_acceptance_verification_required", "failed", "blocking", "Unified Release Program Continuity Acceptance requirement needs a verification report.")
        return
    if not signoff_binding_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_acceptance_binding_required", "failed", "blocking", "Unified Release Program Continuity Acceptance requirement needs a signoff binding.")
        return
    if not kit_path or not kit_verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_acceptance_kit_required", "failed", "blocking", "Unified Release Program Continuity Acceptance requirement needs source Continuity Distribution Kit evidence.")
        return
    zip_path = Path(archive_path)
    try:
        from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_acceptance_package,
        )

        verification_report = read_json(Path(archive_verification_report_path))
        runtime_report = verify_unified_release_program_continuity_acceptance_package(
            zip_path,
            strict=True,
            require_current_kit=True,
            require_signed=True,
            require_quorum=True,
            continuity_kit_path=kit_path,
            continuity_kit_verification_report_path=kit_verification_report_path,
            signoff_binding_path=signoff_binding_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_acceptance_readable", "failed", "blocking", f"Unified Release Program Continuity Acceptance evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_acceptance",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_command_center_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    command_center_path: Path | str | None,
    verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> None:
    if not command_center_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_required", "failed", "blocking", "Unified Release Program Continuity Command Center requirement needs a ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_verification_required", "failed", "blocking", "Unified Release Program Continuity Command Center requirement needs a verification report.")
        return
    if not external_evidence_manifest_path:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_manifest_required", "failed", "blocking", "Unified Release Program Continuity Command Center requirement needs an external evidence manifest.")
        return
    zip_path = Path(command_center_path)
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_package,
        )

        verification_report = read_json(Path(verification_report_path))
        runtime_report = verify_unified_release_program_continuity_command_center_package(
            zip_path,
            strict=True,
            deep=True,
            require_ready=True,
            evidence_manifest_path=external_evidence_manifest_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_readable", "failed", "blocking", f"Unified Release Program Continuity Command Center evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_command_center",
        ga_check,
        zip_path,
        verification_report,
        runtime_report,
        UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_command_center_signoff_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> None:
    if not all((archive_path, verification_report_path, signoff_binding_path, command_center_path, command_center_verification_report_path, external_evidence_manifest_path)):
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_signoff_required", "failed", "blocking", "Continuity Command Center signoff requires Archive, verification report, independent binding, current Command Center, and evidence manifest.")
        return
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import (
            COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_signoff_package,
        )

        zip_path = _as_path(archive_path)
        external = read_json(_as_path(verification_report_path))
        runtime = verify_unified_release_program_continuity_command_center_signoff_package(
            zip_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=signoff_binding_path,
            command_center_zip_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
            command_center_external_evidence_manifest_path=external_evidence_manifest_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_signoff_readable", "failed", "blocking", f"Continuity Command Center signoff evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_command_center_signoff",
        ga_check,
        zip_path,
        external,
        runtime,
        COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_command_center_acceptance_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
    acceptance_signoff_binding_path: Path | str | None,
    review_pack_path: Path | str | None,
    review_pack_verification_report_path: Path | str | None,
    accepted_evidence_dir: Path | str | None,
    response_proof_dir: Path | str | None,
    command_center_signoff_archive_path: Path | str | None,
    command_center_signoff_archive_verification_report_path: Path | str | None,
    command_center_final_handoff_path: Path | str | None,
    command_center_final_handoff_verification_report_path: Path | str | None,
    command_center_signoff_binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    command_center_evidence_manifest_path: Path | str | None,
) -> None:
    required_paths = (
        archive_path,
        verification_report_path,
        acceptance_signoff_binding_path,
        review_pack_path,
        review_pack_verification_report_path,
        accepted_evidence_dir,
        response_proof_dir,
        command_center_signoff_archive_path,
        command_center_signoff_archive_verification_report_path,
        command_center_final_handoff_path,
        command_center_final_handoff_verification_report_path,
        command_center_signoff_binding_path,
        command_center_path,
        command_center_verification_report_path,
        command_center_evidence_manifest_path,
    )
    if not all(required_paths):
        _add_check(
            checks,
            "ga_readiness_unified_release_program_continuity_command_center_acceptance_required",
            "failed",
            "blocking",
            "Receiver Acceptance requires Archive, independent binding, response proofs, accepted evidence, Review Pack, and current v12.10 evidence.",
        )
        return
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import (
            ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_package,
        )

        zip_path = _as_path(archive_path)
        external = read_json(_as_path(verification_report_path))
        runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
            zip_path,
            strict=True,
            require_signed=True,
            signoff_binding_path=acceptance_signoff_binding_path,
            review_pack_path=review_pack_path,
            review_pack_verification_report_path=review_pack_verification_report_path,
            accepted_evidence_dir=accepted_evidence_dir,
            response_proof_dir=response_proof_dir,
            command_center_signoff_archive_path=command_center_signoff_archive_path,
            command_center_signoff_archive_verification_report_path=command_center_signoff_archive_verification_report_path,
            command_center_final_handoff_path=command_center_final_handoff_path,
            command_center_final_handoff_verification_report_path=command_center_final_handoff_verification_report_path,
            command_center_signoff_binding_path=command_center_signoff_binding_path,
            command_center_path=command_center_path,
            command_center_verification_report_path=command_center_verification_report_path,
            command_center_evidence_manifest_path=command_center_evidence_manifest_path,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_unified_release_program_continuity_command_center_acceptance_readable", "failed", "blocking", f"Receiver Acceptance evidence could not be read: {exc}")
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_command_center_acceptance",
        ga_check,
        zip_path,
        external,
        runtime,
        ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    )

def _verify_unified_release_program_continuity_command_center_acceptance_change_evidence(
    checks: list[DomainDocument],
    ga_check: DomainDocument,
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
    acceptance_archive_path: Path | str | None,
    acceptance_verification_report_path: Path | str | None,
    acceptance_signoff_binding_path: Path | str | None,
    previous_acceptance_root: Path | str | None,
) -> None:
    required_paths = (
        archive_path,
        verification_report_path,
        acceptance_archive_path,
        acceptance_verification_report_path,
        acceptance_signoff_binding_path,
    )
    if not all(required_paths):
        _add_check(
            checks,
            "ga_readiness_unified_release_program_continuity_command_center_acceptance_change_required",
            "failed",
            "blocking",
            "Receiver Acceptance Change Control requires current lifecycle and Receiver Acceptance evidence.",
        )
        return
    try:
        from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_change_package,
        )

        zip_path = _as_path(archive_path)
        external = read_json(_as_path(verification_report_path))
        runtime = verify_unified_release_program_continuity_command_center_acceptance_change_package(
            zip_path,
            strict=True,
            require_current_acceptance=True,
            acceptance_archive_path=acceptance_archive_path,
            acceptance_verification_report_path=acceptance_verification_report_path,
            acceptance_signoff_binding_path=acceptance_signoff_binding_path,
            previous_acceptance_root=previous_acceptance_root,
            require_reset_proofs=True,
        )
    except Exception as exc:
        _add_check(
            checks,
            "ga_readiness_unified_release_program_continuity_command_center_acceptance_change_readable",
            "failed",
            "blocking",
            f"Receiver Acceptance Change Control evidence could not be read: {exc}",
        )
        return
    _verify_external_package_binding(
        checks,
        "ga_readiness_unified_release_program_continuity_command_center_acceptance_change_control",
        ga_check,
        zip_path,
        external,
        runtime,
        UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
    )
