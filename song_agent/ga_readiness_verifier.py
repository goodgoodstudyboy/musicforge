from __future__ import annotations

import json
import re
import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_agent.ga_readiness import GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok
from song_agent.audio_campaign_archive_verifier import (
    AUDIO_CAMPAIGN_ARCHIVE_PACKAGE_TYPE,
    verify_audio_campaign_archive_package,
)
from song_agent.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package
from song_agent.release_audio_certification_verifier import (
    RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_certification_package,
)
from song_agent.release_audio_timeline_verifier import (
    RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_timeline_package,
)
from song_agent.release_audio_regression_verifier import (
    RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_regression_package,
)
from song_agent.release_audio_baseline_governance_verifier import (
    RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_baseline_registry_package,
)
from song_agent.release_audio_regression_response_verifier import (
    RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_regression_response_package,
)
from song_agent.release_audio_quality_observatory_verifier import (
    RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_quality_observatory_package,
)
from song_agent.release_audio_quality_actions_verifier import (
    RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_quality_action_queue_package,
)
from song_agent.release_audio_quality_action_signoff_verifier import (
    RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_quality_action_queue_signoff_archive_package,
)
from song_agent.release_audio_command_center_verifier import (
    RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_command_center_package,
)
from song_agent.music_acceptance import AcceptanceStore
from song_agent.music_acceptance import stable_hash
from song_agent.projectio import read_json, write_json
from song_agent.releases import stable_hash as release_stable_hash

UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
from song_agent.trust_operations_final_readiness_verifier import (
    TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    verify_trust_operations_final_handoff_package,
)


GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"

_SENSITIVE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|githubkey\.txt)", re.IGNORECASE)


def verify_ga_readiness_report(
    report_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_manual_acceptance: bool = False,
    require_audio_campaign: bool = False,
    require_audio_campaign_remediation: bool = False,
    require_release_audio_certification: bool = False,
    require_release_audio_timeline: bool = False,
    require_release_audio_regression_guard: bool = False,
    require_release_audio_baseline_governance: bool = False,
    require_release_audio_regression_response: bool = False,
    require_release_audio_quality_observatory: bool = False,
    require_release_audio_quality_action_queue: bool = False,
    require_final_readiness: bool = False,
    manual_acceptance_report_path: Path | str | None = None,
    audio_campaign_archive_path: Path | str | None = None,
    audio_campaign_archive_verification_report_path: Path | str | None = None,
    audio_campaign_remediation_path: Path | str | None = None,
    audio_campaign_remediation_verification_report_path: Path | str | None = None,
    release_audio_certification_path: Path | str | None = None,
    release_audio_certification_verification_report_path: Path | str | None = None,
    release_audio_timeline_path: Path | str | None = None,
    release_audio_timeline_verification_report_path: Path | str | None = None,
    release_audio_regression_path: Path | str | None = None,
    release_audio_regression_verification_report_path: Path | str | None = None,
    release_audio_regression_baseline_timeline_path: Path | str | None = None,
    release_audio_regression_baseline_timeline_verification_report_path: Path | str | None = None,
    release_audio_regression_baseline_certification_path: Path | str | None = None,
    release_audio_regression_baseline_certification_verification_report_path: Path | str | None = None,
    release_audio_regression_current_timeline_path: Path | str | None = None,
    release_audio_regression_current_timeline_verification_report_path: Path | str | None = None,
    release_audio_regression_current_certification_path: Path | str | None = None,
    release_audio_regression_current_certification_verification_report_path: Path | str | None = None,
    release_audio_baseline_registry_path: Path | str | None = None,
    release_audio_baseline_registry_verification_report_path: Path | str | None = None,
    release_audio_regression_response_path: Path | str | None = None,
    release_audio_regression_response_verification_report_path: Path | str | None = None,
    release_audio_quality_observatory_path: Path | str | None = None,
    release_audio_quality_observatory_verification_report_path: Path | str | None = None,
    release_audio_quality_observatory_evidence_root: Path | str | None = None,
    release_audio_quality_action_queue_path: Path | str | None = None,
    release_audio_quality_action_queue_verification_report_path: Path | str | None = None,
    require_release_audio_quality_action_queue_signoff: bool = False,
    release_audio_quality_action_queue_signoff_archive_path: Path | str | None = None,
    release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None = None,
    require_release_audio_command_center: bool = False,
    release_audio_command_center_path: Path | str | None = None,
    release_audio_command_center_verification_report_path: Path | str | None = None,
    require_unified_command_center: bool = False,
    unified_command_center_path: Path | str | None = None,
    unified_command_center_verification_report_path: Path | str | None = None,
    require_unified_command_center_archive: bool = False,
    unified_command_center_archive_path: Path | str | None = None,
    unified_command_center_archive_verification_report_path: Path | str | None = None,
    require_unified_command_center_handoff: bool = False,
    unified_command_center_handoff_path: Path | str | None = None,
    unified_command_center_handoff_verification_report_path: Path | str | None = None,
    require_unified_command_center_continuous_review: bool = False,
    unified_command_center_continuous_review_path: Path | str | None = None,
    unified_command_center_continuous_review_verification_report_path: Path | str | None = None,
    require_unified_command_center_drift_response: bool = False,
    unified_command_center_drift_response_path: Path | str | None = None,
    unified_command_center_drift_response_verification_report_path: Path | str | None = None,
    unified_command_center_drift_source_review_path: Path | str | None = None,
    unified_command_center_drift_source_review_verification_report_path: Path | str | None = None,
    unified_command_center_drift_recheck_review_path: Path | str | None = None,
    unified_command_center_drift_recheck_review_verification_report_path: Path | str | None = None,
    unified_command_center_drift_change_request_binding_report_path: Path | str | None = None,
    require_unified_command_center_evidence_review: bool = False,
    unified_command_center_evidence_review_path: Path | str | None = None,
    unified_command_center_evidence_review_verification_report_path: Path | str | None = None,
    require_unified_command_center_evidence_review_accepted: bool = False,
    unified_command_center_evidence_review_acceptance_path: Path | str | None = None,
    unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None = None,
    unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None = None,
    require_unified_command_center_reviewer_decision_board: bool = False,
    unified_command_center_reviewer_decision_board_path: Path | str | None = None,
    unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None = None,
    require_unified_command_center_reviewer_decision_board_signed: bool = True,
    require_unified_command_center_reviewer_decision_board_quorum: bool = True,
    unified_command_center_reviewer_decision_board_evidence_review_path: Path | str | None = None,
    unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None = None,
    unified_command_center_reviewer_decision_board_accepted_evidence_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    require_unified_release_program_handoff: bool = False,
    unified_release_program_handoff_path: Path | str | None = None,
    unified_release_program_handoff_verification_report_path: Path | str | None = None,
    unified_release_program_handoff_external_evidence_manifest_path: Path | str | None = None,
    unified_release_program_handoff_signoff_binding_path: Path | str | None = None,
    require_unified_release_program_vault: bool = False,
    unified_release_program_vault_path: Path | str | None = None,
    unified_release_program_vault_verification_report_path: Path | str | None = None,
    unified_release_program_vault_anchor_path: Path | str | None = None,
    require_unified_release_program_vault_operations: bool = False,
    unified_release_program_vault_operations_path: Path | str | None = None,
    unified_release_program_vault_operations_verification_report_path: Path | str | None = None,
    unified_release_program_vault_operations_signoff_binding_path: Path | str | None = None,
    require_unified_release_program_continuity: bool = False,
    unified_release_program_continuity_path: Path | str | None = None,
    unified_release_program_continuity_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_signoff_binding_path: Path | str | None = None,
    require_unified_release_program_continuity_kit: bool = False,
    unified_release_program_continuity_kit_path: Path | str | None = None,
    unified_release_program_continuity_kit_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None = None,
    require_unified_release_program_continuity_acceptance: bool = False,
    unified_release_program_continuity_acceptance_path: Path | str | None = None,
    unified_release_program_continuity_acceptance_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None = None,
    require_unified_release_program_continuity_command_center: bool = False,
    unified_release_program_continuity_command_center_path: Path | str | None = None,
    unified_release_program_continuity_command_center_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None = None,
    require_unified_release_program_continuity_command_center_signoff: bool = False,
    unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None = None,
    unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None = None,
    require_unified_release_program_continuity_command_center_acceptance: bool = False,
    unified_release_program_continuity_command_center_acceptance_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None = None,
    require_unified_release_program_continuity_command_center_acceptance_change_control: bool = False,
    unified_release_program_continuity_command_center_acceptance_change_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None = None,
    unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None = None,
    unified_release_program_continuity_command_center_final_handoff_path: Path | str | None = None,
    unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None = None,
    unified_command_center_signoff_binding_path: Path | str | None = None,
    unified_release_path: Path | str | None = None,
    unified_release_verification_report_path: Path | str | None = None,
    unified_distribution_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_submission_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    unified_release_operations_path: Path | str | None = None,
    unified_release_operations_verification_report_path: Path | str | None = None,
    unified_trust_operations_hub_path: Path | str | None = None,
    unified_trust_operations_hub_verification_report_path: Path | str | None = None,
    unified_public_trust_center_path: Path | str | None = None,
    unified_public_trust_center_verification_report_path: Path | str | None = None,
    unified_maintenance_backup_path: Path | str | None = None,
    unified_maintenance_backup_verification_report_path: Path | str | None = None,
    require_no_critical_audio_quality_risk: bool = False,
    final_handoff_package_path: Path | str | None = None,
    final_handoff_verification_report_path: Path | str | None = None,
    release_check_latest_report_path: Path | str | None = None,
    release_check_ga_report_path: Path | str | None = None,
) -> dict[str, Any]:
    target = Path(report_path)
    checks: list[dict[str, Any]] = []
    try:
        report = read_json(target)
    except Exception as exc:
        report = {}
        _add_check(checks, "ga_readiness_report_readable", "failed", "blocking", f"GA readiness report could not be read: {exc}")

    if report:
        _add_check(
            checks,
            "ga_readiness_package_type",
            "passed" if report.get("package_type") == GA_READINESS_PACKAGE_TYPE else "failed",
            "blocking",
            "GA readiness report package type is valid." if report.get("package_type") == GA_READINESS_PACKAGE_TYPE else "GA readiness report package type is invalid.",
        )
        _add_check(
            checks,
            "ga_readiness_schema_version",
            "passed" if report.get("schema_version") == GA_READINESS_SCHEMA_VERSION else "failed",
            "blocking",
            "GA readiness report schema version is supported." if report.get("schema_version") == GA_READINESS_SCHEMA_VERSION else "GA readiness report schema version is unsupported.",
        )
        _add_check(
            checks,
            "ga_readiness_integrity",
            "passed" if ga_readiness_integrity_ok(report) else "failed",
            "blocking",
            "GA readiness report integrity hash matches." if ga_readiness_integrity_ok(report) else "GA readiness report integrity hash mismatch.",
        )
        status = str(report.get("status") or "unknown")
        allowed_statuses = {"ready", "warning"} if not strict else {"ready"}
        status_severity = "blocking" if status == "blocked" or strict or require_ready else "warning"
        _add_check(
            checks,
            "ga_readiness_status_allowed",
            "passed" if status in allowed_statuses else "failed",
            status_severity,
            f"GA readiness status is {status}.",
            {"status": status, "allowed": sorted(allowed_statuses)},
        )
        if require_ready:
            _add_check(
                checks,
                "ga_readiness_require_ready",
                "passed" if status == "ready" else "failed",
                "blocking",
                "GA readiness is ready." if status == "ready" else "GA readiness is not ready.",
            )
        _add_check(
            checks,
            "ga_readiness_redaction",
            "passed" if not _SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)) else "failed",
            "blocking",
            "GA readiness report contains no obvious token strings." if not _SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)) else "GA readiness report contains a token-like string.",
        )
        checks_by_id = {str(item.get("check_id")): item for item in report.get("checks", []) if isinstance(item, dict)}
        if require_manual_acceptance:
            _verify_manual_acceptance_evidence(checks, checks_by_id.get("ga.acceptance_manual", {}), manual_acceptance_report_path)
        if require_audio_campaign:
            _verify_audio_campaign_evidence(
                checks,
                checks_by_id.get("ga.audio_campaign", {}),
                audio_campaign_archive_path,
                audio_campaign_archive_verification_report_path,
            )
        if require_audio_campaign_remediation:
            _verify_audio_campaign_remediation_evidence(
                checks,
                checks_by_id.get("ga.audio_campaign_remediation", {}),
                audio_campaign_remediation_path,
                audio_campaign_remediation_verification_report_path,
            )
        if require_release_audio_certification:
            _verify_release_audio_certification_evidence(
                checks,
                checks_by_id.get("ga.release_audio_certification", {}),
                release_audio_certification_path,
                release_audio_certification_verification_report_path,
            )
        if require_release_audio_timeline:
            _verify_release_audio_timeline_evidence(
                checks,
                checks_by_id.get("ga.release_audio_timeline", {}),
                release_audio_timeline_path,
                release_audio_timeline_verification_report_path,
                release_audio_certification_path,
                release_audio_certification_verification_report_path,
            )
        if require_release_audio_regression_guard:
            _verify_release_audio_regression_evidence(
                checks,
                checks_by_id.get("ga.release_audio_regression_guard", {}),
                release_audio_regression_path,
                release_audio_regression_verification_report_path,
                release_audio_regression_baseline_timeline_path,
                release_audio_regression_baseline_timeline_verification_report_path,
                release_audio_regression_baseline_certification_path,
                release_audio_regression_baseline_certification_verification_report_path,
                release_audio_regression_current_timeline_path or release_audio_timeline_path,
                release_audio_regression_current_timeline_verification_report_path or release_audio_timeline_verification_report_path,
                release_audio_regression_current_certification_path or release_audio_certification_path,
                release_audio_regression_current_certification_verification_report_path or release_audio_certification_verification_report_path,
            )
        if require_release_audio_baseline_governance:
            _verify_release_audio_baseline_governance_evidence(
                checks,
                checks_by_id.get("ga.release_audio_baseline_governance", {}),
                release_audio_baseline_registry_path,
                release_audio_baseline_registry_verification_report_path,
            )
        if require_release_audio_regression_response:
            _verify_release_audio_regression_response_evidence(
                checks,
                checks_by_id.get("ga.release_audio_regression_response", {}),
                release_audio_regression_response_path,
                release_audio_regression_response_verification_report_path,
                release_audio_regression_path,
                release_audio_regression_verification_report_path,
                release_audio_regression_baseline_timeline_path,
                release_audio_regression_baseline_timeline_verification_report_path,
                release_audio_regression_baseline_certification_path,
                release_audio_regression_baseline_certification_verification_report_path,
                release_audio_regression_current_timeline_path or release_audio_timeline_path,
                release_audio_regression_current_timeline_verification_report_path or release_audio_timeline_verification_report_path,
                release_audio_regression_current_certification_path or release_audio_certification_path,
                release_audio_regression_current_certification_verification_report_path or release_audio_certification_verification_report_path,
            )
        if require_release_audio_quality_observatory:
            _verify_release_audio_quality_observatory_evidence(
                checks,
                checks_by_id.get("ga.release_audio_quality_observatory", {}),
                release_audio_quality_observatory_path,
                release_audio_quality_observatory_verification_report_path,
                release_audio_quality_observatory_evidence_root,
                require_no_critical_audio_quality_risk=require_no_critical_audio_quality_risk or require_release_audio_quality_observatory,
            )
        if require_release_audio_quality_action_queue:
            _verify_release_audio_quality_action_queue_evidence(
                checks,
                checks_by_id.get("ga.release_audio_quality_action_queue", {}),
                release_audio_quality_action_queue_path,
                release_audio_quality_action_queue_verification_report_path,
                release_audio_quality_observatory_path,
                release_audio_quality_observatory_verification_report_path,
                release_audio_quality_observatory_evidence_root,
            )
        if require_release_audio_quality_action_queue_signoff:
            _verify_release_audio_quality_action_queue_signoff_evidence(
                checks,
                checks_by_id.get("ga.release_audio_quality_action_queue_signoff", {}),
                release_audio_quality_action_queue_signoff_archive_path,
                release_audio_quality_action_queue_signoff_verification_report_path,
                release_audio_quality_action_queue_path,
                release_audio_quality_action_queue_verification_report_path,
                release_audio_quality_observatory_path,
                release_audio_quality_observatory_verification_report_path,
                release_audio_quality_observatory_evidence_root,
            )
        if require_release_audio_command_center:
            _verify_release_audio_command_center_evidence(
                checks,
                checks_by_id.get("ga.release_audio_command_center", {}),
                release_audio_command_center_path,
                release_audio_command_center_verification_report_path,
                release_audio_certification_path,
                release_audio_certification_verification_report_path,
                release_audio_timeline_path,
                release_audio_timeline_verification_report_path,
                release_audio_regression_path,
                release_audio_regression_verification_report_path,
                release_audio_baseline_registry_path,
                release_audio_baseline_registry_verification_report_path,
                release_audio_regression_response_path,
                release_audio_regression_response_verification_report_path,
                release_audio_quality_observatory_path,
                release_audio_quality_observatory_verification_report_path,
                release_audio_quality_action_queue_path,
                release_audio_quality_action_queue_verification_report_path,
                release_audio_quality_action_queue_signoff_archive_path,
                release_audio_quality_action_queue_signoff_verification_report_path,
                release_audio_quality_observatory_evidence_root,
            )
        if require_unified_command_center:
            _verify_unified_command_center_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center", {}),
                unified_command_center_path,
                unified_command_center_verification_report_path,
                unified_release_path,
                unified_release_verification_report_path,
                release_audio_command_center_path,
                release_audio_command_center_verification_report_path,
                unified_distribution_paths,
                unified_distribution_verification_report_paths,
                unified_submission_paths,
                unified_submission_verification_report_paths,
                unified_release_operations_path,
                unified_release_operations_verification_report_path,
                unified_trust_operations_hub_path,
                unified_trust_operations_hub_verification_report_path,
                unified_public_trust_center_path,
                unified_public_trust_center_verification_report_path,
                unified_maintenance_backup_path,
                unified_maintenance_backup_verification_report_path,
            )
        if require_unified_command_center_archive:
            _verify_unified_command_center_archive_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_archive", {}),
                unified_command_center_archive_path,
                unified_command_center_archive_verification_report_path,
                unified_command_center_path,
                unified_command_center_verification_report_path,
            )
        if require_unified_command_center_handoff:
            _verify_unified_command_center_handoff_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_handoff", {}),
                unified_command_center_handoff_path,
                unified_command_center_handoff_verification_report_path,
                unified_command_center_archive_path,
                unified_command_center_archive_verification_report_path,
            )
        if require_unified_command_center_continuous_review:
            _verify_unified_command_center_continuous_review_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_continuous_review", {}),
                unified_command_center_continuous_review_path,
                unified_command_center_continuous_review_verification_report_path,
                unified_command_center_archive_path,
                unified_command_center_archive_verification_report_path,
                unified_command_center_handoff_path,
                unified_command_center_handoff_verification_report_path,
                unified_command_center_path,
                unified_command_center_verification_report_path,
            )
        if require_unified_command_center_drift_response:
            _verify_unified_command_center_drift_response_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_drift_response", {}),
                unified_command_center_drift_response_path,
                unified_command_center_drift_response_verification_report_path,
                unified_command_center_drift_source_review_path,
                unified_command_center_drift_source_review_verification_report_path,
                unified_command_center_drift_recheck_review_path,
                unified_command_center_drift_recheck_review_verification_report_path,
                unified_command_center_drift_change_request_binding_report_path,
                unified_command_center_signoff_binding_path,
                unified_command_center_archive_path,
                unified_command_center_archive_verification_report_path,
                unified_command_center_handoff_path,
                unified_command_center_handoff_verification_report_path,
                unified_command_center_path,
                unified_command_center_verification_report_path,
            )
        if require_unified_command_center_evidence_review:
            _verify_unified_command_center_evidence_review_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_evidence_review", {}),
                unified_command_center_evidence_review_path,
                unified_command_center_evidence_review_verification_report_path,
                require_unified_command_center_evidence_review_accepted,
                unified_command_center_evidence_review_acceptance_path,
                unified_command_center_evidence_review_acceptance_verification_report_path,
                unified_command_center_evidence_review_acceptance_response_verification_report_path,
                unified_command_center_path,
                unified_command_center_verification_report_path,
                unified_command_center_archive_path,
                unified_command_center_archive_verification_report_path,
                unified_command_center_handoff_path,
                unified_command_center_handoff_verification_report_path,
                unified_command_center_continuous_review_path,
                unified_command_center_continuous_review_verification_report_path,
                unified_command_center_drift_response_path,
                unified_command_center_drift_response_verification_report_path,
                unified_command_center_drift_source_review_path,
                unified_command_center_drift_source_review_verification_report_path,
                unified_command_center_drift_recheck_review_path,
                unified_command_center_drift_recheck_review_verification_report_path,
                unified_command_center_drift_change_request_binding_report_path,
                unified_command_center_signoff_binding_path,
                release_check_latest_report_path or release_check_ga_report_path,
            )
        if require_unified_command_center_reviewer_decision_board:
            _verify_unified_command_center_reviewer_decision_board_evidence(
                checks,
                checks_by_id.get("ga.unified_command_center_reviewer_decision_board", {}),
                unified_command_center_reviewer_decision_board_path,
                unified_command_center_reviewer_decision_board_verification_report_path,
                require_unified_command_center_reviewer_decision_board_signed,
                require_unified_command_center_reviewer_decision_board_quorum,
                unified_command_center_reviewer_decision_board_evidence_review_path or unified_command_center_evidence_review_path,
                unified_command_center_reviewer_decision_board_evidence_review_verification_report_path or unified_command_center_evidence_review_verification_report_path,
                unified_command_center_reviewer_decision_board_accepted_evidence_paths,
                unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths,
                unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths,
            )
        if require_unified_release_program_handoff:
            _verify_unified_release_program_handoff_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_handoff", {}),
                unified_release_program_handoff_path,
                unified_release_program_handoff_verification_report_path,
                unified_release_program_handoff_external_evidence_manifest_path,
                unified_release_program_handoff_signoff_binding_path,
            )
        if require_unified_release_program_vault:
            _verify_unified_release_program_vault_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_vault", {}),
                unified_release_program_vault_path,
                unified_release_program_vault_verification_report_path,
                unified_release_program_vault_anchor_path,
            )
        if require_unified_release_program_vault_operations:
            _verify_unified_release_program_vault_operations_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_vault_operations", {}),
                unified_release_program_vault_operations_path,
                unified_release_program_vault_operations_verification_report_path,
                unified_release_program_vault_operations_signoff_binding_path,
            )
        if require_unified_release_program_continuity:
            _verify_unified_release_program_continuity_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity", {}),
                unified_release_program_continuity_path,
                unified_release_program_continuity_verification_report_path,
                unified_release_program_continuity_signoff_binding_path,
                unified_release_program_vault_operations_path,
                unified_release_program_vault_operations_verification_report_path,
                unified_release_program_vault_operations_signoff_binding_path,
            )
        if require_unified_release_program_continuity_kit:
            _verify_unified_release_program_continuity_kit_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_kit", {}),
                unified_release_program_continuity_kit_path,
                unified_release_program_continuity_kit_verification_report_path,
                unified_release_program_continuity_kit_receiver_receipt_path,
            )
        if require_unified_release_program_continuity_acceptance:
            _verify_unified_release_program_continuity_acceptance_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_acceptance", {}),
                unified_release_program_continuity_acceptance_path,
                unified_release_program_continuity_acceptance_verification_report_path,
                unified_release_program_continuity_acceptance_signoff_binding_path,
                unified_release_program_continuity_kit_path,
                unified_release_program_continuity_kit_verification_report_path,
            )
        if require_unified_release_program_continuity_command_center:
            _verify_unified_release_program_continuity_command_center_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_command_center", {}),
                unified_release_program_continuity_command_center_path,
                unified_release_program_continuity_command_center_verification_report_path,
                unified_release_program_continuity_command_center_external_evidence_manifest_path,
            )
        if require_unified_release_program_continuity_command_center_signoff:
            _verify_unified_release_program_continuity_command_center_signoff_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_command_center_signoff", {}),
                unified_release_program_continuity_command_center_signoff_archive_path,
                unified_release_program_continuity_command_center_signoff_verification_report_path,
                unified_release_program_continuity_command_center_signoff_binding_path,
                unified_release_program_continuity_command_center_path,
                unified_release_program_continuity_command_center_verification_report_path,
                unified_release_program_continuity_command_center_external_evidence_manifest_path,
            )
        if (
            require_unified_release_program_continuity_command_center_acceptance
            or require_unified_release_program_continuity_command_center_acceptance_change_control
        ):
            _verify_unified_release_program_continuity_command_center_acceptance_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_command_center_acceptance", {}),
                unified_release_program_continuity_command_center_acceptance_path,
                unified_release_program_continuity_command_center_acceptance_verification_report_path,
                unified_release_program_continuity_command_center_acceptance_signoff_binding_path,
                unified_release_program_continuity_command_center_acceptance_review_pack_path,
                unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path,
                unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir,
                unified_release_program_continuity_command_center_acceptance_response_proof_dir,
                unified_release_program_continuity_command_center_signoff_archive_path,
                unified_release_program_continuity_command_center_signoff_verification_report_path,
                unified_release_program_continuity_command_center_final_handoff_path,
                unified_release_program_continuity_command_center_final_handoff_verification_report_path,
                unified_release_program_continuity_command_center_signoff_binding_path,
                unified_release_program_continuity_command_center_path,
                unified_release_program_continuity_command_center_verification_report_path,
                unified_release_program_continuity_command_center_external_evidence_manifest_path,
            )
        if require_unified_release_program_continuity_command_center_acceptance_change_control:
            _verify_unified_release_program_continuity_command_center_acceptance_change_evidence(
                checks,
                checks_by_id.get("ga.unified_release_program_continuity_command_center_acceptance_change_control", {}),
                unified_release_program_continuity_command_center_acceptance_change_path,
                unified_release_program_continuity_command_center_acceptance_change_verification_report_path,
                unified_release_program_continuity_command_center_acceptance_path,
                unified_release_program_continuity_command_center_acceptance_verification_report_path,
                unified_release_program_continuity_command_center_acceptance_signoff_binding_path,
                unified_release_program_continuity_command_center_acceptance_previous_root,
            )
        if require_final_readiness:
            _verify_final_readiness_evidence(
                checks,
                checks_by_id.get("ga.trust_final_readiness", {}),
                final_handoff_package_path,
                final_handoff_verification_report_path,
            )

    blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") == "warning" or check.get("severity") == "warning"]
    verification = {
        "package_type": GA_READINESS_VERIFICATION_PACKAGE_TYPE,
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {
            "source_path": str(target.name),
            "ga_status": report.get("status") if isinstance(report, dict) else "missing",
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "checks": checks,
    }
    verification["integrity_hash"] = stable_hash({key: value for key, value in verification.items() if key != "integrity_hash"})
    return verification


def write_ga_readiness_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    target = Path(path)
    write_json(target, report)
    return target


def _verify_manual_acceptance_evidence(checks: list[dict[str, Any]], ga_check: dict[str, Any], report_path: Path | str | None) -> None:
    if not report_path:
        _add_check(
            checks,
            "ga_readiness_manual_acceptance_report_required",
            "failed",
            "blocking",
            "Manual acceptance requirement needs an external music acceptance report.",
        )
        return
    target = Path(report_path)
    try:
        report = read_json(target)
    except Exception as exc:
        _add_check(
            checks,
            "ga_readiness_manual_acceptance_report_readable",
            "failed",
            "blocking",
            f"Manual acceptance report could not be read: {exc}",
        )
        return
    _add_check(checks, "ga_readiness_manual_acceptance_report_readable", "passed", "info", "Manual acceptance report is readable.", {"source_path": target.name})
    suite_id = str(report.get("suite_id") or "")
    verified_report = _verify_acceptance_report_from_store(target, suite_id, report)
    if verified_report:
        report = verified_report
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    report_passed = report.get("status") == "passed"
    verification_passed = verification.get("status") == "passed" and verification.get("source_status") == "passed" and verification.get("content_status") == "passed"
    manual_count = _safe_int(summary.get("manual_accepted_count"))
    synthetic_count = _safe_int(summary.get("synthetic_accepted_count"))
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_status",
        "passed" if report_passed else "failed",
        "blocking",
        "Manual acceptance report is passed." if report_passed else "Manual acceptance report is not passed.",
        {"status": report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_verification",
        "passed" if verification_passed else "failed",
        "blocking",
        "Manual acceptance report source/content verification is passed." if verification_passed else "Manual acceptance report source/content verification is not passed.",
        {
            "status": verification.get("status"),
            "source_status": verification.get("source_status"),
            "content_status": verification.get("content_status"),
        },
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_store_binding",
        "passed" if verified_report and verification_passed else "failed",
        "blocking",
        "Manual acceptance report matches the current AcceptanceStore source." if verified_report and verification_passed else "Manual acceptance report is not bound to current AcceptanceStore source.",
        {"suite_id": suite_id},
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_manual_review",
        "passed" if manual_count > 0 else "failed",
        "blocking",
        "Manual human listening acceptance is present." if manual_count > 0 else "Manual human listening acceptance is missing.",
        {"manual_accepted_count": manual_count, "synthetic_accepted_count": synthetic_count},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    latest = detail.get("latest") if isinstance(detail.get("latest"), dict) else {}
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and _safe_int(detail.get("manual_ready_count")) > 0
        and (not latest or latest.get("suite_id") == report.get("suite_id"))
        and (not latest or latest.get("status") == report.get("status"))
        and (not latest or _safe_int(latest.get("manual_accepted_count")) == manual_count)
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness manual acceptance check matches the external report." if ga_binding_ok else "GA readiness manual acceptance check does not match the external report.",
        {"ga_check_status": ga_check.get("status"), "suite_id": report.get("suite_id"), "ga_latest_suite_id": latest.get("suite_id")},
    )


def _verify_final_readiness_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
    package_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not package_path:
        _add_check(checks, "ga_readiness_final_handoff_package_required", "failed", "blocking", "Final readiness requirement needs an external Final Handoff ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_final_handoff_verification_required", "failed", "blocking", "Final readiness requirement needs an external Final Handoff verification report.")
        return
    zip_path = Path(package_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_final_handoff_verification_readable", "failed", "blocking", f"Final Handoff verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_final_handoff_verification_readable", "passed", "info", "Final Handoff verification report is readable.", {"source_path": report_path.name})
    try:
        package_verification = verify_trust_operations_final_handoff_package(zip_path, strict=True, require_signed=True)
    except Exception as exc:
        package_verification = {"status": "failed", "error": str(exc)}
    manifest = _read_final_handoff_manifest(zip_path)
    zip_sha = _sha256_file(zip_path) if zip_path.exists() else None
    zip_size = zip_path.stat().st_size if zip_path.exists() else None
    _add_check(
        checks,
        "ga_readiness_final_handoff_verification_package_type",
        "passed" if verification_report.get("package_type") == TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE else "failed",
        "blocking",
        "Final Handoff verification package type is valid." if verification_report.get("package_type") == TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE else "Final Handoff verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_verification_status",
        "passed" if verification_report.get("status") == "passed" else "failed",
        "blocking",
        "Final Handoff verification report is passed." if verification_report.get("status") == "passed" else "Final Handoff verification report is not passed.",
        {"status": verification_report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_package_self_verification",
        "passed" if package_verification.get("status") == "passed" else "failed",
        "blocking",
        "Final Handoff ZIP self-verification is passed." if package_verification.get("status") == "passed" else "Final Handoff ZIP self-verification failed.",
        {"status": package_verification.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_zip_binding",
        "passed"
        if verification_report.get("zip_sha256") == zip_sha and verification_report.get("zip_size_bytes") == zip_size and verification_report.get("manifest_hash") == manifest.get("integrity_hash")
        else "failed",
        "blocking",
        "Final Handoff verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == zip_sha and verification_report.get("zip_size_bytes") == zip_size and verification_report.get("manifest_hash") == manifest.get("integrity_hash") else "Final Handoff verification report does not match the ZIP and manifest.",
        {"zip_sha256": zip_sha, "zip_size_bytes": zip_size, "manifest_hash": manifest.get("integrity_hash")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("package_type") == verification_report.get("package_type")
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness final readiness check matches the external Final Handoff verification report." if ga_binding_ok else "GA readiness final readiness check does not match the external Final Handoff verification report.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )


def _verify_audio_campaign_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    current_summary = current_verification.get("summary") if isinstance(current_verification.get("summary"), dict) else {}
    report_summary = verification_report.get("summary") if isinstance(verification_report.get("summary"), dict) else {}
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    gate = detail.get("gate") if isinstance(detail.get("gate"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    current_summary = current_verification.get("summary") if isinstance(current_verification.get("summary"), dict) else {}
    _add_check(
        checks,
        "ga_readiness_release_audio_certification_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Certification verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Certification verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "track_count": current_summary.get("track_count")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    current_summary = current_verification.get("summary") if isinstance(current_verification.get("summary"), dict) else {}
    _add_check(
        checks,
        "ga_readiness_release_audio_timeline_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Timeline verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Timeline verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "track_count": current_summary.get("track_count")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    current_summary = current_verification.get("summary") if isinstance(current_verification.get("summary"), dict) else {}
    _add_check(
        checks,
        "ga_readiness_release_audio_regression_zip_binding",
        "passed" if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "failed",
        "blocking",
        "Release Audio Regression verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == _sha256_file(zip_path) and verification_report.get("manifest_hash") == current_verification.get("manifest_hash") else "Release Audio Regression verification report does not match the ZIP and manifest.",
        {"zip_sha256": _sha256_file(zip_path), "manifest_hash": current_verification.get("manifest_hash"), "release_id": current_summary.get("release_id"), "baseline_release_id": current_summary.get("baseline_release_id")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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


def _verify_release_audio_baseline_governance_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
            **current_args,
        )
    except Exception as exc:
        _add_check(checks, "ga_readiness_release_audio_regression_response_readable", "failed", "blocking", f"Release Audio Regression Response evidence could not be read: {exc}")
        return
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_verifier import (
            UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
            verify_unified_command_center_package,
        )

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
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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


def _verify_unified_command_center_archive_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_archive_verifier import (
            UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_command_center_archive_package,
        )

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_handoff_verifier import (
            UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE,
            verify_unified_command_center_handoff_package,
        )

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_evidence_review_verifier import (
            verify_unified_command_center_evidence_review_acceptance_package,
            verify_unified_command_center_evidence_review_package,
        )

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_command_center_reviewer_decision_board_verifier import verify_unified_command_center_reviewer_decision_board_package

        verification_report = read_json(Path(board_verification_report_path))
        runtime_report = verify_unified_command_center_reviewer_decision_board_package(
            zip_path,
            strict=True,
            require_signed=require_signed,
            require_quorum=require_quorum,
            evidence_review_path=evidence_review_path,
            evidence_review_verification_report_path=evidence_review_verification_report_path,
            accepted_evidence_paths=accepted_evidence_paths or [],
            accepted_evidence_verification_report_paths=accepted_evidence_verification_report_paths or [],
            accepted_evidence_response_verification_report_paths=accepted_evidence_response_verification_report_paths or [],
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_handoff_verifier import UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_handoff_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package

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


def _verify_unified_release_program_vault_operations_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_distribution_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_distribution_package

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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_acceptance_verifier import (
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_command_center_verifier import (
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_command_center_signoff_verifier import (
            COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_signoff_package,
        )

        zip_path = Path(archive_path)
        external = read_json(Path(verification_report_path))
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_command_center_acceptance_verifier import (
            ARCHIVE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_package,
        )

        zip_path = Path(archive_path)
        external = read_json(Path(verification_report_path))
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
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
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
        from song_agent.unified_release_program_continuity_command_center_acceptance_change_verifier import (
            UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
            verify_unified_release_program_continuity_command_center_acceptance_change_package,
        )

        zip_path = Path(archive_path)
        external = read_json(Path(verification_report_path))
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


def _verify_external_package_binding(
    checks: list[dict[str, Any]],
    prefix: str,
    ga_check: dict[str, Any],
    zip_path: Path,
    verification_report: dict[str, Any],
    runtime_report: dict[str, Any],
    expected_package_type: str,
) -> None:
    integrity_ok = verification_report.get("integrity_hash") == release_stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
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


def _read_final_handoff_manifest(zip_path: Path) -> dict[str, Any]:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open("trust-operations-final-readiness-manifest.json") as file:
                return json.loads(file.read().decode("utf-8"))
    except Exception:
        return {}


def _verification_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
    }


def _verify_acceptance_report_from_store(report_path: Path, suite_id: str, report: dict[str, Any]) -> dict[str, Any] | None:
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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _add_check(checks: list[dict[str, Any]], check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}})
