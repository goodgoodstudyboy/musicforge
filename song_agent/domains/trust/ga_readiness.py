from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import os as os
import platform as platform
import re as re
import subprocess as subprocess
import sys as sys
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any, Callable as Callable

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




DEFAULT_GA_REPORT_PATH = Path("runs") / "ga-readiness" / "ga-readiness-report.json"

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


class GAReadinessError(RuntimeError):
    pass


def _build_ga_readiness_report_part_01(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _split_state['root'] = Path(repo_root or Path.cwd()).resolve()
    _split_state['checks']: list[dict[str, Any]] = []
    _split_state['source']: dict[str, Any] = {'repo_root': '.', 'strict': strict, 'policy_id': policy, 'require_manual_acceptance': require_manual_acceptance, 'require_audio': require_audio, 'require_audio_campaign': require_audio_campaign, 'require_audio_campaign_remediation': require_audio_campaign_remediation, 'require_release_audio_certification': require_release_audio_certification, 'require_release_audio_timeline': require_release_audio_timeline, 'require_release_audio_regression_guard': require_release_audio_regression_guard, 'require_release_audio_baseline_governance': require_release_audio_baseline_governance, 'require_release_audio_regression_response': require_release_audio_regression_response, 'require_release_audio_quality_observatory': require_release_audio_quality_observatory, 'require_release_audio_quality_action_queue': require_release_audio_quality_action_queue, 'require_release_audio_quality_action_queue_signoff': require_release_audio_quality_action_queue_signoff, 'require_release_audio_command_center': require_release_audio_command_center, 'require_unified_command_center': require_unified_command_center, 'require_unified_command_center_archive': require_unified_command_center_archive, 'require_unified_command_center_handoff': require_unified_command_center_handoff, 'require_unified_command_center_continuous_review': require_unified_command_center_continuous_review, 'require_unified_command_center_drift_response': require_unified_command_center_drift_response, 'require_unified_command_center_evidence_review': require_unified_command_center_evidence_review, 'require_unified_command_center_evidence_review_accepted': require_unified_command_center_evidence_review_accepted, 'require_unified_command_center_reviewer_decision_board': require_unified_command_center_reviewer_decision_board, 'require_unified_command_center_reviewer_decision_board_signed': require_unified_command_center_reviewer_decision_board_signed, 'require_unified_command_center_reviewer_decision_board_quorum': require_unified_command_center_reviewer_decision_board_quorum, 'require_unified_release_program_handoff': require_unified_release_program_handoff, 'require_unified_release_program_vault': require_unified_release_program_vault, 'require_unified_release_program_vault_operations': require_unified_release_program_vault_operations, 'require_unified_release_program_continuity': require_unified_release_program_continuity, 'require_unified_release_program_continuity_kit': require_unified_release_program_continuity_kit, 'require_unified_release_program_continuity_acceptance': require_unified_release_program_continuity_acceptance, 'require_unified_release_program_continuity_command_center': require_unified_release_program_continuity_command_center, 'require_unified_release_program_continuity_command_center_signoff': require_unified_release_program_continuity_command_center_signoff, 'require_no_critical_audio_quality_risk': require_no_critical_audio_quality_risk, 'audio_campaign_id': audio_campaign_id, 'require_final_readiness': require_final_readiness}
    version_summary = _version_summary(_split_state['root'])
    _add_check(_split_state['checks'], 'ga.version_consistency', 'passed' if version_summary.get('consistent') else 'failed', 'blocking', 'Package version matches pyproject.toml.' if version_summary.get('consistent') else 'Package version does not match pyproject.toml.', version_summary)
    _split_state['git_summary'] = _git_summary(_split_state['root'])
    git_status = 'passed'
    git_severity = 'warning'
    git_message = 'Working tree is clean.'
    if _split_state['git_summary'].get('state') != 'clean':
        git_message = 'Working tree is not clean.'
        if strict and (not allow_dirty):
            git_status = 'failed'
            git_severity = 'blocking'
        else:
            git_status = 'warning'
    _add_check(_split_state['checks'], 'ga.git_clean', git_status, git_severity, git_message, _split_state['git_summary'])
    _split_state['doctor_summary'] = _doctor_summary(_split_state['root'])
    _add_check(_split_state['checks'], 'ga.doctor', 'passed' if _split_state['doctor_summary'].get('status') == 'passed' else 'failed', 'blocking', 'Core local setup is usable.' if _split_state['doctor_summary'].get('status') == 'passed' else 'Core local setup has blocking issues.', _split_state['doctor_summary'])
    docs_summary = _docs_summary(_split_state['root'])
    _add_check(_split_state['checks'], 'ga.docs_present', 'passed' if not docs_summary.get('missing') else 'failed', 'blocking', 'GA/LTS docs are present.' if not docs_summary.get('missing') else 'Required GA/LTS docs are missing.', docs_summary)
    secrets_summary = _secret_summary(_split_state['root'])
    _add_check(_split_state['checks'], 'ga.secret_scan', 'passed' if not secrets_summary.get('findings') else 'failed', 'blocking', 'No obvious token or local key-path strings found in GA docs.' if not secrets_summary.get('findings') else 'Potential secret or local key-path string found.', secrets_summary)
    _split_state['renderer_summary'] = _renderer_summary(_split_state['root'])
    return (False, None)

def _build_ga_readiness_report_part_02(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    renderer_status = 'passed'
    renderer_severity = 'info'
    renderer_message = 'Renderer profile is configured.' if _split_state['renderer_summary'].get('status') == 'configured' else 'Renderer profile is not configured.'
    if require_audio and _split_state['renderer_summary'].get('status') != 'configured':
        renderer_status = 'failed'
        renderer_severity = 'blocking'
    elif _split_state['renderer_summary'].get('status') != 'configured':
        renderer_status = 'warning'
        renderer_severity = 'warning'
    _add_check(_split_state['checks'], 'ga.renderer_audio', renderer_status, renderer_severity, renderer_message, _split_state['renderer_summary'])
    _split_state['provider_summary'] = _provider_summary(_split_state['root'])
    _add_check(_split_state['checks'], 'ga.provider', 'passed' if _split_state['provider_summary'].get('status') in {'configured', 'mock', 'missing'} else 'warning', 'info', 'Provider configuration is optional for deterministic local mode.', _split_state['provider_summary'])
    _split_state['acceptance_summary'] = _acceptance_summary(_split_state['root'])
    acceptance_status = _acceptance_check_status(_split_state['acceptance_summary'], require_manual_acceptance=require_manual_acceptance, require_audio=require_audio)
    _add_check(_split_state['checks'], 'ga.acceptance_manual', acceptance_status['status'], acceptance_status['severity'], acceptance_status['message'], _split_state['acceptance_summary'])
    _split_state['audio_campaign_summary'] = _audio_campaign_summary(audio_campaign_id, required=require_audio_campaign, archive_zip_path=audio_campaign_archive_zip_path, archive_verification_report_path=audio_campaign_archive_verification_report_path)
    _add_check(_split_state['checks'], 'ga.audio_campaign', 'passed' if _split_state['audio_campaign_summary'].get('status') == 'passed' else 'failed' if require_audio_campaign else 'warning', 'blocking' if require_audio_campaign else 'warning', 'Audio Campaign governance evidence is passed.' if _split_state['audio_campaign_summary'].get('status') == 'passed' else 'Audio Campaign governance evidence is missing or not passed.', _split_state['audio_campaign_summary'])
    _split_state['remediation_summary'] = _audio_campaign_remediation_summary(required=require_audio_campaign_remediation, remediation_zip_path=audio_campaign_remediation_zip_path, remediation_verification_report_path=audio_campaign_remediation_verification_report_path)
    _add_check(_split_state['checks'], 'ga.audio_campaign_remediation', 'passed' if _split_state['remediation_summary'].get('status') == 'passed' else 'failed' if require_audio_campaign_remediation else 'warning', 'blocking' if require_audio_campaign_remediation else 'warning', 'Audio Campaign remediation evidence is passed.' if _split_state['remediation_summary'].get('status') == 'passed' else 'Audio Campaign remediation evidence is missing or not passed.', _split_state['remediation_summary'])
    _split_state['certification_summary'] = _release_audio_certification_summary(required=require_release_audio_certification, certification_zip_path=release_audio_certification_zip_path, certification_verification_report_path=release_audio_certification_verification_report_path)
    _add_check(_split_state['checks'], 'ga.release_audio_certification', 'passed' if _split_state['certification_summary'].get('status') == 'passed' else 'failed' if require_release_audio_certification else 'warning', 'blocking' if require_release_audio_certification else 'warning', 'Release Audio Certification evidence is passed.' if _split_state['certification_summary'].get('status') == 'passed' else 'Release Audio Certification evidence is missing or not passed.', _split_state['certification_summary'])
    _split_state['timeline_summary'] = _release_audio_timeline_summary(required=require_release_audio_timeline, timeline_zip_path=release_audio_timeline_zip_path, timeline_verification_report_path=release_audio_timeline_verification_report_path, certification_zip_path=release_audio_certification_zip_path, certification_verification_report_path=release_audio_certification_verification_report_path)
    _add_check(_split_state['checks'], 'ga.release_audio_timeline', 'passed' if _split_state['timeline_summary'].get('status') == 'passed' else 'failed' if require_release_audio_timeline else 'warning', 'blocking' if require_release_audio_timeline else 'warning', 'Release Audio Timeline evidence is passed.' if _split_state['timeline_summary'].get('status') == 'passed' else 'Release Audio Timeline evidence is missing or not passed.', _split_state['timeline_summary'])
    return (False, None)

def _build_ga_readiness_report_part_03(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _split_state['regression_summary'] = _release_audio_regression_summary(required=require_release_audio_regression_guard, regression_zip_path=release_audio_regression_zip_path, regression_verification_report_path=release_audio_regression_verification_report_path, baseline_timeline_path=release_audio_regression_baseline_timeline_path, baseline_timeline_verification_report_path=release_audio_regression_baseline_timeline_verification_report_path, baseline_certification_path=release_audio_regression_baseline_certification_path, baseline_certification_verification_report_path=release_audio_regression_baseline_certification_verification_report_path, current_timeline_path=release_audio_regression_current_timeline_path or release_audio_timeline_zip_path, current_timeline_verification_report_path=release_audio_regression_current_timeline_verification_report_path or release_audio_timeline_verification_report_path, current_certification_path=release_audio_regression_current_certification_path or release_audio_certification_zip_path, current_certification_verification_report_path=release_audio_regression_current_certification_verification_report_path or release_audio_certification_verification_report_path)
    _add_check(_split_state['checks'], 'ga.release_audio_regression_guard', 'passed' if _split_state['regression_summary'].get('status') == 'passed' else 'failed' if require_release_audio_regression_guard else 'warning', 'blocking' if require_release_audio_regression_guard else 'warning', 'Release Audio Regression Guard evidence is passed.' if _split_state['regression_summary'].get('status') == 'passed' else 'Release Audio Regression Guard evidence is missing or not passed.', _split_state['regression_summary'])
    _split_state['baseline_governance_summary'] = _release_audio_baseline_governance_summary(required=require_release_audio_baseline_governance, registry_zip_path=release_audio_baseline_registry_zip_path, registry_verification_report_path=release_audio_baseline_registry_verification_report_path)
    _add_check(_split_state['checks'], 'ga.release_audio_baseline_governance', 'passed' if _split_state['baseline_governance_summary'].get('status') == 'passed' else 'failed' if require_release_audio_baseline_governance else 'warning', 'blocking' if require_release_audio_baseline_governance else 'warning', 'Release Audio Baseline Governance evidence is passed.' if _split_state['baseline_governance_summary'].get('status') == 'passed' else 'Release Audio Baseline Governance evidence is missing or not passed.', _split_state['baseline_governance_summary'])
    _split_state['regression_response_summary'] = _release_audio_regression_response_summary(required=require_release_audio_regression_response, response_zip_path=release_audio_regression_response_zip_path, response_verification_report_path=release_audio_regression_response_verification_report_path, regression_zip_path=release_audio_regression_response_regression_zip_path or release_audio_regression_zip_path, regression_verification_report_path=release_audio_regression_response_regression_verification_report_path or release_audio_regression_verification_report_path, baseline_timeline_path=release_audio_regression_response_baseline_timeline_path or release_audio_regression_baseline_timeline_path, baseline_timeline_verification_report_path=release_audio_regression_response_baseline_timeline_verification_report_path or release_audio_regression_baseline_timeline_verification_report_path, baseline_certification_path=release_audio_regression_response_baseline_certification_path or release_audio_regression_baseline_certification_path, baseline_certification_verification_report_path=release_audio_regression_response_baseline_certification_verification_report_path or release_audio_regression_baseline_certification_verification_report_path, current_timeline_path=release_audio_regression_response_current_timeline_path or release_audio_regression_current_timeline_path or release_audio_timeline_zip_path, current_timeline_verification_report_path=release_audio_regression_response_current_timeline_verification_report_path or release_audio_regression_current_timeline_verification_report_path or release_audio_timeline_verification_report_path, current_certification_path=release_audio_regression_response_current_certification_path or release_audio_regression_current_certification_path or release_audio_certification_zip_path, current_certification_verification_report_path=release_audio_regression_response_current_certification_verification_report_path or release_audio_regression_current_certification_verification_report_path or release_audio_certification_verification_report_path)
    _add_check(_split_state['checks'], 'ga.release_audio_regression_response', 'passed' if _split_state['regression_response_summary'].get('status') == 'passed' else 'failed' if require_release_audio_regression_response else 'warning', 'blocking' if require_release_audio_regression_response else 'warning', 'Release Audio Regression Response evidence is passed.' if _split_state['regression_response_summary'].get('status') == 'passed' else 'Release Audio Regression Response evidence is missing or not passed.', _split_state['regression_response_summary'])
    _split_state['quality_observatory_summary'] = _release_audio_quality_observatory_summary(required=require_release_audio_quality_observatory, observatory_zip_path=release_audio_quality_observatory_zip_path, observatory_verification_report_path=release_audio_quality_observatory_verification_report_path, evidence_root=release_audio_quality_observatory_evidence_root, require_no_critical_risk=require_no_critical_audio_quality_risk or require_release_audio_quality_observatory)
    _add_check(_split_state['checks'], 'ga.release_audio_quality_observatory', 'passed' if _split_state['quality_observatory_summary'].get('status') == 'passed' else 'failed' if require_release_audio_quality_observatory else 'warning', 'blocking' if require_release_audio_quality_observatory else 'warning', 'Release Audio Quality Observatory evidence is passed.' if _split_state['quality_observatory_summary'].get('status') == 'passed' else 'Release Audio Quality Observatory evidence is missing or not passed.', _split_state['quality_observatory_summary'])
    _split_state['quality_action_queue_summary'] = _release_audio_quality_action_queue_summary(required=require_release_audio_quality_action_queue, queue_zip_path=release_audio_quality_action_queue_zip_path, queue_verification_report_path=release_audio_quality_action_queue_verification_report_path, observatory_zip_path=release_audio_quality_observatory_zip_path, observatory_verification_report_path=release_audio_quality_observatory_verification_report_path, evidence_root=release_audio_quality_observatory_evidence_root)
    _add_check(_split_state['checks'], 'ga.release_audio_quality_action_queue', 'passed' if _split_state['quality_action_queue_summary'].get('status') == 'passed' else 'failed' if require_release_audio_quality_action_queue else 'warning', 'blocking' if require_release_audio_quality_action_queue else 'warning', 'Release Audio Quality Action Queue evidence is passed.' if _split_state['quality_action_queue_summary'].get('status') == 'passed' else 'Release Audio Quality Action Queue evidence is missing or not passed.', _split_state['quality_action_queue_summary'])
    return (False, None)

def _build_ga_readiness_report_part_04(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _split_state['quality_action_queue_signoff_summary'] = _release_audio_quality_action_queue_signoff_summary(required=require_release_audio_quality_action_queue_signoff, archive_zip_path=release_audio_quality_action_queue_signoff_archive_path, archive_verification_report_path=release_audio_quality_action_queue_signoff_verification_report_path, queue_zip_path=release_audio_quality_action_queue_zip_path, queue_verification_report_path=release_audio_quality_action_queue_verification_report_path, observatory_zip_path=release_audio_quality_observatory_zip_path, observatory_verification_report_path=release_audio_quality_observatory_verification_report_path, evidence_root=release_audio_quality_observatory_evidence_root)
    _add_check(_split_state['checks'], 'ga.release_audio_quality_action_queue_signoff', 'passed' if _split_state['quality_action_queue_signoff_summary'].get('status') == 'passed' else 'failed' if require_release_audio_quality_action_queue_signoff else 'warning', 'blocking' if require_release_audio_quality_action_queue_signoff else 'warning', 'Release Audio Quality Action Queue signoff archive is passed.' if _split_state['quality_action_queue_signoff_summary'].get('status') == 'passed' else 'Release Audio Quality Action Queue signoff archive is missing or not passed.', _split_state['quality_action_queue_signoff_summary'])
    _split_state['command_center_summary'] = _release_audio_command_center_summary(required=require_release_audio_command_center, command_center_zip_path=release_audio_command_center_zip_path, command_center_verification_report_path=release_audio_command_center_verification_report_path, certification_zip_path=release_audio_certification_zip_path, certification_verification_report_path=release_audio_certification_verification_report_path, timeline_zip_path=release_audio_timeline_zip_path, timeline_verification_report_path=release_audio_timeline_verification_report_path, regression_zip_path=release_audio_regression_zip_path, regression_verification_report_path=release_audio_regression_verification_report_path, baseline_registry_zip_path=release_audio_baseline_registry_zip_path, baseline_registry_verification_report_path=release_audio_baseline_registry_verification_report_path, regression_response_zip_path=release_audio_regression_response_zip_path, regression_response_verification_report_path=release_audio_regression_response_verification_report_path, observatory_zip_path=release_audio_quality_observatory_zip_path, observatory_verification_report_path=release_audio_quality_observatory_verification_report_path, action_queue_zip_path=release_audio_quality_action_queue_zip_path, action_queue_verification_report_path=release_audio_quality_action_queue_verification_report_path, action_queue_signoff_archive_path=release_audio_quality_action_queue_signoff_archive_path, action_queue_signoff_verification_report_path=release_audio_quality_action_queue_signoff_verification_report_path, evidence_root=release_audio_quality_observatory_evidence_root)
    _add_check(_split_state['checks'], 'ga.release_audio_command_center', 'passed' if _split_state['command_center_summary'].get('status') == 'passed' else 'failed' if require_release_audio_command_center else 'warning', 'blocking' if require_release_audio_command_center else 'warning', 'Release Audio Command Center is passed.' if _split_state['command_center_summary'].get('status') == 'passed' else 'Release Audio Command Center is missing or not passed.', _split_state['command_center_summary'])
    _split_state['unified_summary'] = _unified_command_center_summary(required=require_unified_command_center, command_center_zip_path=unified_command_center_zip_path, command_center_verification_report_path=unified_command_center_verification_report_path, release_zip_path=unified_release_zip_path, release_verification_report_path=unified_release_verification_report_path, release_audio_command_center_zip_path=release_audio_command_center_zip_path, release_audio_command_center_verification_report_path=release_audio_command_center_verification_report_path, distribution_zip_paths=unified_distribution_zip_paths, distribution_verification_report_paths=unified_distribution_verification_report_paths, submission_zip_paths=unified_submission_zip_paths, submission_verification_report_paths=unified_submission_verification_report_paths, release_operations_zip_path=unified_release_operations_zip_path, release_operations_verification_report_path=unified_release_operations_verification_report_path, trust_operations_hub_zip_path=unified_trust_operations_hub_zip_path, trust_operations_hub_verification_report_path=unified_trust_operations_hub_verification_report_path, public_trust_center_zip_path=unified_public_trust_center_zip_path, public_trust_center_verification_report_path=unified_public_trust_center_verification_report_path, maintenance_backup_zip_path=unified_maintenance_backup_zip_path, maintenance_backup_verification_report_path=unified_maintenance_backup_verification_report_path, ga_readiness_report_path=None, release_check_report_path=release_check_ga_report_path or release_check_latest_report_path)
    _add_check(_split_state['checks'], 'ga.unified_command_center', 'passed' if _split_state['unified_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center else 'warning', 'blocking' if require_unified_command_center else 'warning', 'Unified Command Center is passed.' if _split_state['unified_summary'].get('status') == 'passed' else 'Unified Command Center is missing or not passed.', _split_state['unified_summary'])
    _split_state['unified_archive_summary'] = _unified_command_center_archive_summary(required=require_unified_command_center_archive, archive_zip_path=unified_command_center_archive_zip_path, archive_verification_report_path=unified_command_center_archive_verification_report_path, command_center_zip_path=unified_command_center_zip_path, command_center_verification_report_path=unified_command_center_verification_report_path, signoff_binding_path=unified_command_center_signoff_binding_path)
    return (False, None)

def _build_ga_readiness_report_part_05(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _add_check(_split_state['checks'], 'ga.unified_command_center_archive', 'passed' if _split_state['unified_archive_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_archive else 'warning', 'blocking' if require_unified_command_center_archive else 'warning', 'Unified Command Center Archive is passed.' if _split_state['unified_archive_summary'].get('status') == 'passed' else 'Unified Command Center Archive is missing or not passed.', _split_state['unified_archive_summary'])
    _split_state['unified_handoff_summary'] = _unified_command_center_handoff_summary(required=require_unified_command_center_handoff, handoff_zip_path=unified_command_center_handoff_zip_path, handoff_verification_report_path=unified_command_center_handoff_verification_report_path, archive_zip_path=unified_command_center_archive_zip_path, archive_verification_report_path=unified_command_center_archive_verification_report_path)
    _add_check(_split_state['checks'], 'ga.unified_command_center_handoff', 'passed' if _split_state['unified_handoff_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_handoff else 'warning', 'blocking' if require_unified_command_center_handoff else 'warning', 'Unified Command Center Handoff is passed.' if _split_state['unified_handoff_summary'].get('status') == 'passed' else 'Unified Command Center Handoff is missing or not passed.', _split_state['unified_handoff_summary'])
    _split_state['unified_review_summary'] = _unified_command_center_continuous_review_summary(required=require_unified_command_center_continuous_review, review_zip_path=unified_command_center_continuous_review_zip_path, review_verification_report_path=unified_command_center_continuous_review_verification_report_path, archive_zip_path=unified_command_center_archive_zip_path, archive_verification_report_path=unified_command_center_archive_verification_report_path, handoff_zip_path=unified_command_center_handoff_zip_path, handoff_verification_report_path=unified_command_center_handoff_verification_report_path, command_center_zip_path=unified_command_center_zip_path, command_center_verification_report_path=unified_command_center_verification_report_path, signoff_binding_path=unified_command_center_signoff_binding_path)
    _add_check(_split_state['checks'], 'ga.unified_command_center_continuous_review', 'passed' if _split_state['unified_review_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_continuous_review else 'warning', 'blocking' if require_unified_command_center_continuous_review else 'warning', 'Unified Command Center Continuous Review is passed.' if _split_state['unified_review_summary'].get('status') == 'passed' else 'Unified Command Center Continuous Review is missing or not passed.', _split_state['unified_review_summary'])
    _split_state['unified_drift_response_summary'] = _unified_command_center_drift_response_summary(required=require_unified_command_center_drift_response, response_zip_path=unified_command_center_drift_response_zip_path, response_verification_report_path=unified_command_center_drift_response_verification_report_path, source_review_zip_path=unified_command_center_drift_source_review_zip_path, source_review_verification_report_path=unified_command_center_drift_source_review_verification_report_path, recheck_review_zip_path=unified_command_center_drift_recheck_review_zip_path, recheck_review_verification_report_path=unified_command_center_drift_recheck_review_verification_report_path, change_request_binding_report_path=unified_command_center_drift_change_request_binding_report_path, archive_zip_path=unified_command_center_archive_zip_path, archive_verification_report_path=unified_command_center_archive_verification_report_path, handoff_zip_path=unified_command_center_handoff_zip_path, handoff_verification_report_path=unified_command_center_handoff_verification_report_path, command_center_zip_path=unified_command_center_zip_path, command_center_verification_report_path=unified_command_center_verification_report_path, signoff_binding_path=unified_command_center_signoff_binding_path)
    _add_check(_split_state['checks'], 'ga.unified_command_center_drift_response', 'passed' if _split_state['unified_drift_response_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_drift_response else 'warning', 'blocking' if require_unified_command_center_drift_response else 'warning', 'Unified Command Center Drift Response is passed.' if _split_state['unified_drift_response_summary'].get('status') == 'passed' else 'Unified Command Center Drift Response is missing or not passed.', _split_state['unified_drift_response_summary'])
    return (False, None)

def _build_ga_readiness_report_part_06(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _split_state['unified_evidence_review_summary'] = _unified_command_center_evidence_review_summary(required=require_unified_command_center_evidence_review, review_zip_path=unified_command_center_evidence_review_zip_path, review_verification_report_path=unified_command_center_evidence_review_verification_report_path, require_accepted=require_unified_command_center_evidence_review_accepted, acceptance_zip_path=unified_command_center_evidence_review_acceptance_zip_path, acceptance_verification_report_path=unified_command_center_evidence_review_acceptance_verification_report_path, acceptance_response_verification_report_path=unified_command_center_evidence_review_acceptance_response_verification_report_path, ucc_zip_path=unified_command_center_zip_path, ucc_verification_report_path=unified_command_center_verification_report_path, archive_zip_path=unified_command_center_archive_zip_path, archive_verification_report_path=unified_command_center_archive_verification_report_path, handoff_zip_path=unified_command_center_handoff_zip_path, handoff_verification_report_path=unified_command_center_handoff_verification_report_path, continuous_review_zip_path=unified_command_center_continuous_review_zip_path, continuous_review_verification_report_path=unified_command_center_continuous_review_verification_report_path, drift_response_zip_path=unified_command_center_drift_response_zip_path, drift_response_verification_report_path=unified_command_center_drift_response_verification_report_path, source_review_zip_path=unified_command_center_drift_source_review_zip_path, source_review_verification_report_path=unified_command_center_drift_source_review_verification_report_path, recheck_review_zip_path=unified_command_center_drift_recheck_review_zip_path, recheck_review_verification_report_path=unified_command_center_drift_recheck_review_verification_report_path, drift_change_request_binding_report_path=unified_command_center_drift_change_request_binding_report_path, signoff_binding_path=unified_command_center_signoff_binding_path, ga_readiness_report_path=None, release_check_report_path=release_check_latest_report_path or release_check_ga_report_path)
    _add_check(_split_state['checks'], 'ga.unified_command_center_evidence_review', 'passed' if _split_state['unified_evidence_review_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_evidence_review else 'warning', 'blocking' if require_unified_command_center_evidence_review else 'warning', 'Unified Command Center Evidence Review is passed.' if _split_state['unified_evidence_review_summary'].get('status') == 'passed' else 'Unified Command Center Evidence Review is missing or not passed.', _split_state['unified_evidence_review_summary'])
    _split_state['unified_decision_board_summary'] = _unified_command_center_reviewer_decision_board_summary(required=require_unified_command_center_reviewer_decision_board, board_zip_path=unified_command_center_reviewer_decision_board_zip_path, board_verification_report_path=unified_command_center_reviewer_decision_board_verification_report_path, require_signed=require_unified_command_center_reviewer_decision_board_signed, require_quorum=require_unified_command_center_reviewer_decision_board_quorum, evidence_review_zip_path=unified_command_center_reviewer_decision_board_evidence_review_zip_path or unified_command_center_evidence_review_zip_path, evidence_review_verification_report_path=unified_command_center_reviewer_decision_board_evidence_review_verification_report_path or unified_command_center_evidence_review_verification_report_path, accepted_evidence_zip_paths=unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, accepted_evidence_verification_report_paths=unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, accepted_evidence_response_verification_report_paths=unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths)
    _add_check(_split_state['checks'], 'ga.unified_command_center_reviewer_decision_board', 'passed' if _split_state['unified_decision_board_summary'].get('status') == 'passed' else 'failed' if require_unified_command_center_reviewer_decision_board else 'warning', 'blocking' if require_unified_command_center_reviewer_decision_board else 'warning', 'Unified Command Center Reviewer Decision Board is passed.' if _split_state['unified_decision_board_summary'].get('status') == 'passed' else 'Unified Command Center Reviewer Decision Board is missing or not passed.', _split_state['unified_decision_board_summary'])
    _split_state['unified_release_program_handoff_summary'] = _unified_release_program_handoff_summary(required=require_unified_release_program_handoff, handoff_zip_path=unified_release_program_handoff_zip_path, handoff_verification_report_path=unified_release_program_handoff_verification_report_path, external_evidence_manifest_path=unified_release_program_handoff_external_evidence_manifest_path, handoff_signoff_binding_path=unified_release_program_handoff_signoff_binding_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_handoff', 'passed' if _split_state['unified_release_program_handoff_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_handoff else 'warning', 'blocking' if require_unified_release_program_handoff else 'warning', 'Unified Release Program Handoff is passed.' if _split_state['unified_release_program_handoff_summary'].get('status') == 'passed' else 'Unified Release Program Handoff is missing or not passed.', _split_state['unified_release_program_handoff_summary'])
    _split_state['unified_release_program_vault_summary'] = _unified_release_program_vault_summary(required=require_unified_release_program_vault, vault_zip_path=unified_release_program_vault_zip_path, vault_verification_report_path=unified_release_program_vault_verification_report_path, vault_anchor_path=unified_release_program_vault_anchor_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_vault', 'passed' if _split_state['unified_release_program_vault_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_vault else 'warning', 'blocking' if require_unified_release_program_vault else 'warning', 'Unified Release Program Evidence Vault is passed.' if _split_state['unified_release_program_vault_summary'].get('status') == 'passed' else 'Unified Release Program Evidence Vault is missing or not passed.', _split_state['unified_release_program_vault_summary'])
    _split_state['unified_release_program_vault_operations_summary'] = _unified_release_program_vault_operations_summary(required=require_unified_release_program_vault_operations, archive_zip_path=unified_release_program_vault_operations_zip_path, archive_verification_report_path=unified_release_program_vault_operations_verification_report_path, signoff_binding_path=unified_release_program_vault_operations_signoff_binding_path)
    return (False, None)

def _build_ga_readiness_report_part_07(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    _add_check(_split_state['checks'], 'ga.unified_release_program_vault_operations', 'passed' if _split_state['unified_release_program_vault_operations_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_vault_operations else 'warning', 'blocking' if require_unified_release_program_vault_operations else 'warning', 'Unified Release Program Vault Operations is passed.' if _split_state['unified_release_program_vault_operations_summary'].get('status') == 'passed' else 'Unified Release Program Vault Operations is missing or not passed.', _split_state['unified_release_program_vault_operations_summary'])
    _split_state['unified_release_program_continuity_summary'] = _unified_release_program_continuity_summary(required=require_unified_release_program_continuity, archive_zip_path=unified_release_program_continuity_zip_path, archive_verification_report_path=unified_release_program_continuity_verification_report_path, signoff_binding_path=unified_release_program_continuity_signoff_binding_path, vault_operations_archive_path=unified_release_program_vault_operations_zip_path, vault_operations_verification_report_path=unified_release_program_vault_operations_verification_report_path, vault_operations_signoff_binding_path=unified_release_program_vault_operations_signoff_binding_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity', 'passed' if _split_state['unified_release_program_continuity_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_continuity else 'warning', 'blocking' if require_unified_release_program_continuity else 'warning', 'Unified Release Program Continuity is passed.' if _split_state['unified_release_program_continuity_summary'].get('status') == 'passed' else 'Unified Release Program Continuity is missing or not passed.', _split_state['unified_release_program_continuity_summary'])
    _split_state['unified_release_program_continuity_kit_summary'] = _unified_release_program_continuity_kit_summary(required=require_unified_release_program_continuity_kit, kit_zip_path=unified_release_program_continuity_kit_zip_path, kit_verification_report_path=unified_release_program_continuity_kit_verification_report_path, receiver_receipt_path=unified_release_program_continuity_kit_receiver_receipt_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_kit', 'passed' if _split_state['unified_release_program_continuity_kit_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_continuity_kit else 'warning', 'blocking' if require_unified_release_program_continuity_kit else 'warning', 'Unified Release Program Continuity Distribution Kit is passed.' if _split_state['unified_release_program_continuity_kit_summary'].get('status') == 'passed' else 'Unified Release Program Continuity Distribution Kit is missing or not passed.', _split_state['unified_release_program_continuity_kit_summary'])
    _split_state['unified_release_program_continuity_acceptance_summary'] = _unified_release_program_continuity_acceptance_summary(required=require_unified_release_program_continuity_acceptance, archive_zip_path=unified_release_program_continuity_acceptance_zip_path, verification_report_path=unified_release_program_continuity_acceptance_verification_report_path, signoff_binding_path=unified_release_program_continuity_acceptance_signoff_binding_path, kit_zip_path=unified_release_program_continuity_kit_zip_path, kit_verification_report_path=unified_release_program_continuity_kit_verification_report_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_acceptance', 'passed' if _split_state['unified_release_program_continuity_acceptance_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_continuity_acceptance else 'warning', 'blocking' if require_unified_release_program_continuity_acceptance else 'warning', 'Unified Release Program Continuity Acceptance Board is passed.' if _split_state['unified_release_program_continuity_acceptance_summary'].get('status') == 'passed' else 'Unified Release Program Continuity Acceptance Board is missing or not passed.', _split_state['unified_release_program_continuity_acceptance_summary'])
    _split_state['unified_release_program_continuity_command_center_summary'] = _unified_release_program_continuity_command_center_summary(required=require_unified_release_program_continuity_command_center, command_center_zip_path=unified_release_program_continuity_command_center_zip_path, verification_report_path=unified_release_program_continuity_command_center_verification_report_path, external_evidence_manifest_path=unified_release_program_continuity_command_center_external_evidence_manifest_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_command_center', 'passed' if _split_state['unified_release_program_continuity_command_center_summary'].get('status') == 'passed' else 'failed' if require_unified_release_program_continuity_command_center else 'warning', 'blocking' if require_unified_release_program_continuity_command_center else 'warning', 'Unified Release Program Continuity Command Center is ready.' if _split_state['unified_release_program_continuity_command_center_summary'].get('status') == 'passed' else 'Unified Release Program Continuity Command Center is missing or not ready.', _split_state['unified_release_program_continuity_command_center_summary'])
    unified_release_program_continuity_command_center_signoff_summary = _unified_release_program_continuity_command_center_signoff_summary(required=require_unified_release_program_continuity_command_center_signoff, archive_zip_path=unified_release_program_continuity_command_center_signoff_archive_path, verification_report_path=unified_release_program_continuity_command_center_signoff_verification_report_path, signoff_binding_path=unified_release_program_continuity_command_center_signoff_binding_path, command_center_zip_path=unified_release_program_continuity_command_center_zip_path, command_center_verification_report_path=unified_release_program_continuity_command_center_verification_report_path, external_evidence_manifest_path=unified_release_program_continuity_command_center_external_evidence_manifest_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_command_center_signoff', 'passed' if unified_release_program_continuity_command_center_signoff_summary.get('status') == 'passed' else 'failed' if require_unified_release_program_continuity_command_center_signoff else 'warning', 'blocking' if require_unified_release_program_continuity_command_center_signoff else 'warning', 'Unified Release Program Continuity Command Center signoff archive is passed.' if unified_release_program_continuity_command_center_signoff_summary.get('status') == 'passed' else 'Unified Release Program Continuity Command Center signoff archive is missing or not passed.', unified_release_program_continuity_command_center_signoff_summary)
    _split_state['require_receiver_acceptance'] = require_unified_release_program_continuity_command_center_acceptance or require_unified_release_program_continuity_command_center_acceptance_change_control
    return (False, None)

def _build_ga_readiness_report_part_08(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    unified_release_program_continuity_command_center_acceptance_summary = _unified_release_program_continuity_command_center_acceptance_summary(required=_split_state['require_receiver_acceptance'], archive_zip_path=unified_release_program_continuity_command_center_acceptance_archive_path, verification_report_path=unified_release_program_continuity_command_center_acceptance_verification_report_path, acceptance_signoff_binding_path=unified_release_program_continuity_command_center_acceptance_signoff_binding_path, review_pack_path=unified_release_program_continuity_command_center_acceptance_review_pack_path, review_pack_verification_report_path=unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, accepted_evidence_dir=unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, response_proof_dir=unified_release_program_continuity_command_center_acceptance_response_proof_dir, signoff_archive_path=unified_release_program_continuity_command_center_signoff_archive_path, signoff_archive_verification_report_path=unified_release_program_continuity_command_center_signoff_verification_report_path, final_handoff_path=unified_release_program_continuity_command_center_final_handoff_path, final_handoff_verification_report_path=unified_release_program_continuity_command_center_final_handoff_verification_report_path, command_center_signoff_binding_path=unified_release_program_continuity_command_center_signoff_binding_path, command_center_path=unified_release_program_continuity_command_center_zip_path, command_center_verification_report_path=unified_release_program_continuity_command_center_verification_report_path, command_center_evidence_manifest_path=unified_release_program_continuity_command_center_external_evidence_manifest_path)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_command_center_acceptance', 'passed' if unified_release_program_continuity_command_center_acceptance_summary.get('status') == 'passed' else 'failed' if _split_state['require_receiver_acceptance'] else 'warning', 'blocking' if _split_state['require_receiver_acceptance'] else 'warning', 'Unified Release Program Continuity Command Center Receiver Acceptance is passed.' if unified_release_program_continuity_command_center_acceptance_summary.get('status') == 'passed' else 'Receiver Acceptance evidence is missing or not passed.', unified_release_program_continuity_command_center_acceptance_summary)
    receiver_acceptance_change_summary = _unified_release_program_continuity_command_center_acceptance_change_summary(required=require_unified_release_program_continuity_command_center_acceptance_change_control, archive_zip_path=unified_release_program_continuity_command_center_acceptance_change_archive_path, verification_report_path=unified_release_program_continuity_command_center_acceptance_change_verification_report_path, acceptance_archive_path=unified_release_program_continuity_command_center_acceptance_archive_path, acceptance_verification_report_path=unified_release_program_continuity_command_center_acceptance_verification_report_path, acceptance_signoff_binding_path=unified_release_program_continuity_command_center_acceptance_signoff_binding_path, previous_acceptance_root=unified_release_program_continuity_command_center_acceptance_previous_root)
    _add_check(_split_state['checks'], 'ga.unified_release_program_continuity_command_center_acceptance_change_control', 'passed' if receiver_acceptance_change_summary.get('status') == 'passed' else 'failed' if require_unified_release_program_continuity_command_center_acceptance_change_control else 'warning', 'blocking' if require_unified_release_program_continuity_command_center_acceptance_change_control else 'warning', 'Receiver Acceptance Change Control lifecycle is current and passed.' if receiver_acceptance_change_summary.get('status') == 'passed' else 'Receiver Acceptance Change Control evidence is missing or not passed.', receiver_acceptance_change_summary)
    _split_state['latest_summary'] = _release_check_summary(_split_state['root'], report_path=release_check_latest_report_path, profile='latest', run_checks=run_release_checks, skip_tests=skip_tests, executor=release_check_executor)
    _add_check(_split_state['checks'], 'ga.release_check_latest', 'passed' if _split_state['latest_summary'].get('status') == 'passed' else 'warning', 'warning', 'latest release-check profile is passed.' if _split_state['latest_summary'].get('status') == 'passed' else 'latest release-check report is missing or not passed.', _split_state['latest_summary'])
    _split_state['ga_summary'] = _release_check_summary(_split_state['root'], report_path=release_check_ga_report_path, profile='ga', run_checks=run_release_checks, skip_tests=skip_tests, executor=release_check_executor)
    _add_check(_split_state['checks'], 'ga.release_check_ga', 'passed' if _split_state['ga_summary'].get('status') == 'passed' else 'warning', 'warning', 'ga release-check profile is passed.' if _split_state['ga_summary'].get('status') == 'passed' else 'ga release-check report is missing or not passed.', _split_state['ga_summary'])
    _split_state['final_summary'] = _final_readiness_summary(final_handoff_verification_report_path)
    final_status = 'passed' if _split_state['final_summary'].get('status') == 'passed' else 'warning'
    final_severity = 'warning'
    final_message = 'Final Handoff verification report is passed.' if _split_state['final_summary'].get('status') == 'passed' else 'Final Handoff verification report is missing or not passed.'
    if require_final_readiness and _split_state['final_summary'].get('status') != 'passed':
        final_status = 'failed'
        final_severity = 'blocking'
    _add_check(_split_state['checks'], 'ga.trust_final_readiness', final_status, final_severity, final_message, _split_state['final_summary'])
    readiness_scope = locals()
    _split_state['legacy_require_payload'] = normalized_legacy_require_payload({key: value for key, value in readiness_scope.items() if key.startswith('require_')})
    _split_state['enabled_legacy_requires'] = any((bool(value) for value in _split_state['legacy_require_payload'].values()))
    _split_state['effective_policy'] = canonical_ga_policy_id(policy, _split_state['legacy_require_payload'])
    _split_state['policy_summary'] = _evidence_policy_summary(policy, evidence_manifest_path)
    return (False, None)

def _build_ga_readiness_report_part_09(repo_root: Path | str | None, policy: str | None, evidence_manifest_path: Path | str | None, strict: bool, allow_dirty: bool, require_manual_acceptance: bool, require_audio: bool, require_audio_campaign: bool, audio_campaign_id: str | None, audio_campaign_archive_zip_path: Path | str | None, audio_campaign_archive_verification_report_path: Path | str | None, require_audio_campaign_remediation: bool, audio_campaign_remediation_zip_path: Path | str | None, audio_campaign_remediation_verification_report_path: Path | str | None, require_release_audio_certification: bool, release_audio_certification_zip_path: Path | str | None, release_audio_certification_verification_report_path: Path | str | None, require_release_audio_timeline: bool, release_audio_timeline_zip_path: Path | str | None, release_audio_timeline_verification_report_path: Path | str | None, require_release_audio_regression_guard: bool, release_audio_regression_zip_path: Path | str | None, release_audio_regression_verification_report_path: Path | str | None, release_audio_regression_baseline_timeline_path: Path | str | None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_baseline_certification_path: Path | str | None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_current_timeline_path: Path | str | None, release_audio_regression_current_timeline_verification_report_path: Path | str | None, release_audio_regression_current_certification_path: Path | str | None, release_audio_regression_current_certification_verification_report_path: Path | str | None, require_release_audio_baseline_governance: bool, release_audio_baseline_registry_zip_path: Path | str | None, release_audio_baseline_registry_verification_report_path: Path | str | None, require_release_audio_regression_response: bool, release_audio_regression_response_zip_path: Path | str | None, release_audio_regression_response_verification_report_path: Path | str | None, release_audio_regression_response_regression_zip_path: Path | str | None, release_audio_regression_response_regression_verification_report_path: Path | str | None, release_audio_regression_response_baseline_timeline_path: Path | str | None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None, release_audio_regression_response_baseline_certification_path: Path | str | None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None, release_audio_regression_response_current_timeline_path: Path | str | None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None, release_audio_regression_response_current_certification_path: Path | str | None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None, require_release_audio_quality_observatory: bool, release_audio_quality_observatory_zip_path: Path | str | None, release_audio_quality_observatory_verification_report_path: Path | str | None, release_audio_quality_observatory_evidence_root: Path | str | None, require_no_critical_audio_quality_risk: bool, require_release_audio_quality_action_queue: bool, release_audio_quality_action_queue_zip_path: Path | str | None, release_audio_quality_action_queue_verification_report_path: Path | str | None, require_release_audio_quality_action_queue_signoff: bool, release_audio_quality_action_queue_signoff_archive_path: Path | str | None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None, require_release_audio_command_center: bool, release_audio_command_center_zip_path: Path | str | None, release_audio_command_center_verification_report_path: Path | str | None, require_unified_command_center: bool, unified_command_center_zip_path: Path | str | None, unified_command_center_verification_report_path: Path | str | None, unified_command_center_signoff_binding_path: Path | str | None, require_unified_command_center_archive: bool, unified_command_center_archive_zip_path: Path | str | None, unified_command_center_archive_verification_report_path: Path | str | None, require_unified_command_center_handoff: bool, unified_command_center_handoff_zip_path: Path | str | None, unified_command_center_handoff_verification_report_path: Path | str | None, require_unified_command_center_continuous_review: bool, unified_command_center_continuous_review_zip_path: Path | str | None, unified_command_center_continuous_review_verification_report_path: Path | str | None, require_unified_command_center_drift_response: bool, unified_command_center_drift_response_zip_path: Path | str | None, unified_command_center_drift_response_verification_report_path: Path | str | None, unified_command_center_drift_source_review_zip_path: Path | str | None, unified_command_center_drift_source_review_verification_report_path: Path | str | None, unified_command_center_drift_recheck_review_zip_path: Path | str | None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None, unified_command_center_drift_change_request_binding_report_path: Path | str | None, require_unified_command_center_evidence_review: bool, unified_command_center_evidence_review_zip_path: Path | str | None, unified_command_center_evidence_review_verification_report_path: Path | str | None, require_unified_command_center_evidence_review_accepted: bool, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board: bool, unified_command_center_reviewer_decision_board_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None, require_unified_command_center_reviewer_decision_board_signed: bool, require_unified_command_center_reviewer_decision_board_quorum: bool, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, require_unified_release_program_handoff: bool, unified_release_program_handoff_zip_path: Path | str | None, unified_release_program_handoff_verification_report_path: Path | str | None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None, unified_release_program_handoff_signoff_binding_path: Path | str | None, require_unified_release_program_vault: bool, unified_release_program_vault_zip_path: Path | str | None, unified_release_program_vault_verification_report_path: Path | str | None, unified_release_program_vault_anchor_path: Path | str | None, require_unified_release_program_vault_operations: bool, unified_release_program_vault_operations_zip_path: Path | str | None, unified_release_program_vault_operations_verification_report_path: Path | str | None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None, require_unified_release_program_continuity: bool, unified_release_program_continuity_zip_path: Path | str | None, unified_release_program_continuity_verification_report_path: Path | str | None, unified_release_program_continuity_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_kit: bool, unified_release_program_continuity_kit_zip_path: Path | str | None, unified_release_program_continuity_kit_verification_report_path: Path | str | None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None, require_unified_release_program_continuity_acceptance: bool, unified_release_program_continuity_acceptance_zip_path: Path | str | None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center: bool, unified_release_program_continuity_command_center_zip_path: Path | str | None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None, require_unified_release_program_continuity_command_center_signoff: bool, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None, require_unified_release_program_continuity_command_center_acceptance: bool, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None, unified_release_zip_path: Path | str | None, unified_release_verification_report_path: Path | str | None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None, unified_release_operations_zip_path: Path | str | None, unified_release_operations_verification_report_path: Path | str | None, unified_trust_operations_hub_zip_path: Path | str | None, unified_trust_operations_hub_verification_report_path: Path | str | None, unified_public_trust_center_zip_path: Path | str | None, unified_public_trust_center_verification_report_path: Path | str | None, unified_maintenance_backup_zip_path: Path | str | None, unified_maintenance_backup_verification_report_path: Path | str | None, require_final_readiness: bool, final_handoff_verification_report_path: Path | str | None, release_check_latest_report_path: Path | str | None, release_check_ga_report_path: Path | str | None, run_release_checks: bool, skip_tests: bool, release_check_executor: Callable[..., Any] | None, _split_state):
    if not (policy or evidence_manifest_path) and _split_state['enabled_legacy_requires']:
        _split_state['policy_summary'] = evaluate_check_policy(_split_state['effective_policy'], 'ga-readiness', _split_state['checks'])
    converted_requires = legacy_require_summary(_split_state['legacy_require_payload'], _split_state['effective_policy'])
    if policy or evidence_manifest_path or _split_state['enabled_legacy_requires']:
        _split_state['source']['policy_id'] = _split_state['policy_summary'].get('policy_id')
        _split_state['source']['evidence_graph_hash'] = _split_state['policy_summary'].get('graph_hash')
        _split_state['source']['evidence_manifest_hash'] = _split_state['policy_summary'].get('manifest_hash')
        _add_check(_split_state['checks'], 'ga.evidence_policy', 'passed' if _split_state['policy_summary'].get('status') == 'passed' else 'failed', 'blocking', 'Evidence Graph policy gate passed.' if _split_state['policy_summary'].get('status') == 'passed' else 'Evidence Graph policy gate failed.', _split_state['policy_summary'])
    policy_authoritative = bool(policy or evidence_manifest_path or _split_state['enabled_legacy_requires'])
    if policy_authoritative:
        blocking_failures = [] if _split_state['policy_summary'].get('status') == 'passed' else [{'check_id': 'ga.evidence_policy'}]
        warnings = list(_split_state['policy_summary'].get('warnings') or [])
    else:
        blocking_failures = [check for check in _split_state['checks'] if check['status'] == 'failed' and check.get('severity') == 'blocking']
        warnings = [check for check in _split_state['checks'] if check['status'] == 'warning' or check.get('severity') == 'warning']
    status = 'blocked' if blocking_failures else 'warning' if warnings else 'ready'
    report = {'schema_version': GA_READINESS_SCHEMA_VERSION, 'package_type': GA_READINESS_PACKAGE_TYPE, 'generated_at': _now(), 'app_version': __version__, 'status': status, 'summary': {'doctor_status': _split_state['doctor_summary'].get('status', 'unknown'), 'release_check_latest_status': _split_state['latest_summary'].get('status', 'unknown'), 'release_check_ga_status': _split_state['ga_summary'].get('status', 'unknown'), 'acceptance_status': _split_state['acceptance_summary'].get('status', 'missing'), 'audio_campaign_status': _split_state['audio_campaign_summary'].get('status', 'missing'), 'audio_campaign_remediation_status': _split_state['remediation_summary'].get('status', 'missing'), 'release_audio_certification_status': _split_state['certification_summary'].get('status', 'missing'), 'release_audio_timeline_status': _split_state['timeline_summary'].get('status', 'missing'), 'release_audio_regression_guard_status': _split_state['regression_summary'].get('status', 'missing'), 'release_audio_baseline_governance_status': _split_state['baseline_governance_summary'].get('status', 'missing'), 'release_audio_regression_response_status': _split_state['regression_response_summary'].get('status', 'missing'), 'release_audio_quality_observatory_status': _split_state['quality_observatory_summary'].get('status', 'missing'), 'release_audio_quality_action_queue_status': _split_state['quality_action_queue_summary'].get('status', 'missing'), 'release_audio_quality_action_queue_signoff_status': _split_state['quality_action_queue_signoff_summary'].get('status', 'missing'), 'release_audio_command_center_status': _split_state['command_center_summary'].get('status', 'missing'), 'unified_command_center_status': _split_state['unified_summary'].get('status', 'missing'), 'unified_command_center_archive_status': _split_state['unified_archive_summary'].get('status', 'missing'), 'unified_command_center_handoff_status': _split_state['unified_handoff_summary'].get('status', 'missing'), 'unified_command_center_continuous_review_status': _split_state['unified_review_summary'].get('status', 'missing'), 'unified_command_center_drift_response_status': _split_state['unified_drift_response_summary'].get('status', 'missing'), 'unified_command_center_evidence_review_status': _split_state['unified_evidence_review_summary'].get('status', 'missing'), 'unified_command_center_reviewer_decision_board_status': _split_state['unified_decision_board_summary'].get('status', 'missing'), 'unified_release_program_handoff_status': _split_state['unified_release_program_handoff_summary'].get('status', 'missing'), 'unified_release_program_vault_status': _split_state['unified_release_program_vault_summary'].get('status', 'missing'), 'unified_release_program_vault_operations_status': _split_state['unified_release_program_vault_operations_summary'].get('status', 'missing'), 'unified_release_program_continuity_status': _split_state['unified_release_program_continuity_summary'].get('status', 'missing'), 'unified_release_program_continuity_kit_status': _split_state['unified_release_program_continuity_kit_summary'].get('status', 'missing'), 'unified_release_program_continuity_acceptance_status': _split_state['unified_release_program_continuity_acceptance_summary'].get('status', 'missing'), 'unified_release_program_continuity_command_center_status': _split_state['unified_release_program_continuity_command_center_summary'].get('status', 'missing'), 'renderer_status': _split_state['renderer_summary'].get('status', 'unknown'), 'provider_status': _split_state['provider_summary'].get('status', 'unknown'), 'trust_final_readiness_status': _split_state['final_summary'].get('status', 'missing'), 'git_status': _split_state['git_summary'].get('state', 'unknown')}, 'checks': _split_state['checks'], 'next_actions': _next_actions(_split_state['checks']), 'source': _split_state['source'], 'legacy_require_summary': converted_requires}
    report['integrity_hash'] = ga_readiness_integrity_hash(report)
    return (True, sanitize_ga_report(report))
    return (False, None)

def build_ga_readiness_report(*, repo_root: Path | str | None=None, policy: str | None=None, evidence_manifest_path: Path | str | None=None, strict: bool=False, allow_dirty: bool=False, require_manual_acceptance: bool=False, require_audio: bool=False, require_audio_campaign: bool=False, audio_campaign_id: str | None=None, audio_campaign_archive_zip_path: Path | str | None=None, audio_campaign_archive_verification_report_path: Path | str | None=None, require_audio_campaign_remediation: bool=False, audio_campaign_remediation_zip_path: Path | str | None=None, audio_campaign_remediation_verification_report_path: Path | str | None=None, require_release_audio_certification: bool=False, release_audio_certification_zip_path: Path | str | None=None, release_audio_certification_verification_report_path: Path | str | None=None, require_release_audio_timeline: bool=False, release_audio_timeline_zip_path: Path | str | None=None, release_audio_timeline_verification_report_path: Path | str | None=None, require_release_audio_regression_guard: bool=False, release_audio_regression_zip_path: Path | str | None=None, release_audio_regression_verification_report_path: Path | str | None=None, release_audio_regression_baseline_timeline_path: Path | str | None=None, release_audio_regression_baseline_timeline_verification_report_path: Path | str | None=None, release_audio_regression_baseline_certification_path: Path | str | None=None, release_audio_regression_baseline_certification_verification_report_path: Path | str | None=None, release_audio_regression_current_timeline_path: Path | str | None=None, release_audio_regression_current_timeline_verification_report_path: Path | str | None=None, release_audio_regression_current_certification_path: Path | str | None=None, release_audio_regression_current_certification_verification_report_path: Path | str | None=None, require_release_audio_baseline_governance: bool=False, release_audio_baseline_registry_zip_path: Path | str | None=None, release_audio_baseline_registry_verification_report_path: Path | str | None=None, require_release_audio_regression_response: bool=False, release_audio_regression_response_zip_path: Path | str | None=None, release_audio_regression_response_verification_report_path: Path | str | None=None, release_audio_regression_response_regression_zip_path: Path | str | None=None, release_audio_regression_response_regression_verification_report_path: Path | str | None=None, release_audio_regression_response_baseline_timeline_path: Path | str | None=None, release_audio_regression_response_baseline_timeline_verification_report_path: Path | str | None=None, release_audio_regression_response_baseline_certification_path: Path | str | None=None, release_audio_regression_response_baseline_certification_verification_report_path: Path | str | None=None, release_audio_regression_response_current_timeline_path: Path | str | None=None, release_audio_regression_response_current_timeline_verification_report_path: Path | str | None=None, release_audio_regression_response_current_certification_path: Path | str | None=None, release_audio_regression_response_current_certification_verification_report_path: Path | str | None=None, require_release_audio_quality_observatory: bool=False, release_audio_quality_observatory_zip_path: Path | str | None=None, release_audio_quality_observatory_verification_report_path: Path | str | None=None, release_audio_quality_observatory_evidence_root: Path | str | None=None, require_no_critical_audio_quality_risk: bool=False, require_release_audio_quality_action_queue: bool=False, release_audio_quality_action_queue_zip_path: Path | str | None=None, release_audio_quality_action_queue_verification_report_path: Path | str | None=None, require_release_audio_quality_action_queue_signoff: bool=False, release_audio_quality_action_queue_signoff_archive_path: Path | str | None=None, release_audio_quality_action_queue_signoff_verification_report_path: Path | str | None=None, require_release_audio_command_center: bool=False, release_audio_command_center_zip_path: Path | str | None=None, release_audio_command_center_verification_report_path: Path | str | None=None, require_unified_command_center: bool=False, unified_command_center_zip_path: Path | str | None=None, unified_command_center_verification_report_path: Path | str | None=None, unified_command_center_signoff_binding_path: Path | str | None=None, require_unified_command_center_archive: bool=False, unified_command_center_archive_zip_path: Path | str | None=None, unified_command_center_archive_verification_report_path: Path | str | None=None, require_unified_command_center_handoff: bool=False, unified_command_center_handoff_zip_path: Path | str | None=None, unified_command_center_handoff_verification_report_path: Path | str | None=None, require_unified_command_center_continuous_review: bool=False, unified_command_center_continuous_review_zip_path: Path | str | None=None, unified_command_center_continuous_review_verification_report_path: Path | str | None=None, require_unified_command_center_drift_response: bool=False, unified_command_center_drift_response_zip_path: Path | str | None=None, unified_command_center_drift_response_verification_report_path: Path | str | None=None, unified_command_center_drift_source_review_zip_path: Path | str | None=None, unified_command_center_drift_source_review_verification_report_path: Path | str | None=None, unified_command_center_drift_recheck_review_zip_path: Path | str | None=None, unified_command_center_drift_recheck_review_verification_report_path: Path | str | None=None, unified_command_center_drift_change_request_binding_report_path: Path | str | None=None, require_unified_command_center_evidence_review: bool=False, unified_command_center_evidence_review_zip_path: Path | str | None=None, unified_command_center_evidence_review_verification_report_path: Path | str | None=None, require_unified_command_center_evidence_review_accepted: bool=False, unified_command_center_evidence_review_acceptance_zip_path: Path | str | None=None, unified_command_center_evidence_review_acceptance_verification_report_path: Path | str | None=None, unified_command_center_evidence_review_acceptance_response_verification_report_path: Path | str | None=None, require_unified_command_center_reviewer_decision_board: bool=False, unified_command_center_reviewer_decision_board_zip_path: Path | str | None=None, unified_command_center_reviewer_decision_board_verification_report_path: Path | str | None=None, require_unified_command_center_reviewer_decision_board_signed: bool=True, require_unified_command_center_reviewer_decision_board_quorum: bool=True, unified_command_center_reviewer_decision_board_evidence_review_zip_path: Path | str | None=None, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path: Path | str | None=None, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None=None, require_unified_release_program_handoff: bool=False, unified_release_program_handoff_zip_path: Path | str | None=None, unified_release_program_handoff_verification_report_path: Path | str | None=None, unified_release_program_handoff_external_evidence_manifest_path: Path | str | None=None, unified_release_program_handoff_signoff_binding_path: Path | str | None=None, require_unified_release_program_vault: bool=False, unified_release_program_vault_zip_path: Path | str | None=None, unified_release_program_vault_verification_report_path: Path | str | None=None, unified_release_program_vault_anchor_path: Path | str | None=None, require_unified_release_program_vault_operations: bool=False, unified_release_program_vault_operations_zip_path: Path | str | None=None, unified_release_program_vault_operations_verification_report_path: Path | str | None=None, unified_release_program_vault_operations_signoff_binding_path: Path | str | None=None, require_unified_release_program_continuity: bool=False, unified_release_program_continuity_zip_path: Path | str | None=None, unified_release_program_continuity_verification_report_path: Path | str | None=None, unified_release_program_continuity_signoff_binding_path: Path | str | None=None, require_unified_release_program_continuity_kit: bool=False, unified_release_program_continuity_kit_zip_path: Path | str | None=None, unified_release_program_continuity_kit_verification_report_path: Path | str | None=None, unified_release_program_continuity_kit_receiver_receipt_path: Path | str | None=None, require_unified_release_program_continuity_acceptance: bool=False, unified_release_program_continuity_acceptance_zip_path: Path | str | None=None, unified_release_program_continuity_acceptance_verification_report_path: Path | str | None=None, unified_release_program_continuity_acceptance_signoff_binding_path: Path | str | None=None, require_unified_release_program_continuity_command_center: bool=False, unified_release_program_continuity_command_center_zip_path: Path | str | None=None, unified_release_program_continuity_command_center_verification_report_path: Path | str | None=None, unified_release_program_continuity_command_center_external_evidence_manifest_path: Path | str | None=None, require_unified_release_program_continuity_command_center_signoff: bool=False, unified_release_program_continuity_command_center_signoff_archive_path: Path | str | None=None, unified_release_program_continuity_command_center_signoff_verification_report_path: Path | str | None=None, unified_release_program_continuity_command_center_signoff_binding_path: Path | str | None=None, require_unified_release_program_continuity_command_center_acceptance: bool=False, unified_release_program_continuity_command_center_acceptance_archive_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_verification_report_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_signoff_binding_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_review_pack_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_response_proof_dir: Path | str | None=None, require_unified_release_program_continuity_command_center_acceptance_change_control: bool=False, unified_release_program_continuity_command_center_acceptance_change_archive_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_change_verification_report_path: Path | str | None=None, unified_release_program_continuity_command_center_acceptance_previous_root: Path | str | None=None, unified_release_program_continuity_command_center_final_handoff_path: Path | str | None=None, unified_release_program_continuity_command_center_final_handoff_verification_report_path: Path | str | None=None, unified_release_zip_path: Path | str | None=None, unified_release_verification_report_path: Path | str | None=None, unified_distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None=None, unified_release_operations_zip_path: Path | str | None=None, unified_release_operations_verification_report_path: Path | str | None=None, unified_trust_operations_hub_zip_path: Path | str | None=None, unified_trust_operations_hub_verification_report_path: Path | str | None=None, unified_public_trust_center_zip_path: Path | str | None=None, unified_public_trust_center_verification_report_path: Path | str | None=None, unified_maintenance_backup_zip_path: Path | str | None=None, unified_maintenance_backup_verification_report_path: Path | str | None=None, require_final_readiness: bool=False, final_handoff_verification_report_path: Path | str | None=None, release_check_latest_report_path: Path | str | None=None, release_check_ga_report_path: Path | str | None=None, run_release_checks: bool=False, skip_tests: bool=True, release_check_executor: Callable[..., Any] | None=None) -> dict[str, Any]:
    _split_state = {}
    _split_result = _build_ga_readiness_report_part_01(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_02(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_03(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_04(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_05(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_06(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_07(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_08(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _build_ga_readiness_report_part_09(repo_root, policy, evidence_manifest_path, strict, allow_dirty, require_manual_acceptance, require_audio, require_audio_campaign, audio_campaign_id, audio_campaign_archive_zip_path, audio_campaign_archive_verification_report_path, require_audio_campaign_remediation, audio_campaign_remediation_zip_path, audio_campaign_remediation_verification_report_path, require_release_audio_certification, release_audio_certification_zip_path, release_audio_certification_verification_report_path, require_release_audio_timeline, release_audio_timeline_zip_path, release_audio_timeline_verification_report_path, require_release_audio_regression_guard, release_audio_regression_zip_path, release_audio_regression_verification_report_path, release_audio_regression_baseline_timeline_path, release_audio_regression_baseline_timeline_verification_report_path, release_audio_regression_baseline_certification_path, release_audio_regression_baseline_certification_verification_report_path, release_audio_regression_current_timeline_path, release_audio_regression_current_timeline_verification_report_path, release_audio_regression_current_certification_path, release_audio_regression_current_certification_verification_report_path, require_release_audio_baseline_governance, release_audio_baseline_registry_zip_path, release_audio_baseline_registry_verification_report_path, require_release_audio_regression_response, release_audio_regression_response_zip_path, release_audio_regression_response_verification_report_path, release_audio_regression_response_regression_zip_path, release_audio_regression_response_regression_verification_report_path, release_audio_regression_response_baseline_timeline_path, release_audio_regression_response_baseline_timeline_verification_report_path, release_audio_regression_response_baseline_certification_path, release_audio_regression_response_baseline_certification_verification_report_path, release_audio_regression_response_current_timeline_path, release_audio_regression_response_current_timeline_verification_report_path, release_audio_regression_response_current_certification_path, release_audio_regression_response_current_certification_verification_report_path, require_release_audio_quality_observatory, release_audio_quality_observatory_zip_path, release_audio_quality_observatory_verification_report_path, release_audio_quality_observatory_evidence_root, require_no_critical_audio_quality_risk, require_release_audio_quality_action_queue, release_audio_quality_action_queue_zip_path, release_audio_quality_action_queue_verification_report_path, require_release_audio_quality_action_queue_signoff, release_audio_quality_action_queue_signoff_archive_path, release_audio_quality_action_queue_signoff_verification_report_path, require_release_audio_command_center, release_audio_command_center_zip_path, release_audio_command_center_verification_report_path, require_unified_command_center, unified_command_center_zip_path, unified_command_center_verification_report_path, unified_command_center_signoff_binding_path, require_unified_command_center_archive, unified_command_center_archive_zip_path, unified_command_center_archive_verification_report_path, require_unified_command_center_handoff, unified_command_center_handoff_zip_path, unified_command_center_handoff_verification_report_path, require_unified_command_center_continuous_review, unified_command_center_continuous_review_zip_path, unified_command_center_continuous_review_verification_report_path, require_unified_command_center_drift_response, unified_command_center_drift_response_zip_path, unified_command_center_drift_response_verification_report_path, unified_command_center_drift_source_review_zip_path, unified_command_center_drift_source_review_verification_report_path, unified_command_center_drift_recheck_review_zip_path, unified_command_center_drift_recheck_review_verification_report_path, unified_command_center_drift_change_request_binding_report_path, require_unified_command_center_evidence_review, unified_command_center_evidence_review_zip_path, unified_command_center_evidence_review_verification_report_path, require_unified_command_center_evidence_review_accepted, unified_command_center_evidence_review_acceptance_zip_path, unified_command_center_evidence_review_acceptance_verification_report_path, unified_command_center_evidence_review_acceptance_response_verification_report_path, require_unified_command_center_reviewer_decision_board, unified_command_center_reviewer_decision_board_zip_path, unified_command_center_reviewer_decision_board_verification_report_path, require_unified_command_center_reviewer_decision_board_signed, require_unified_command_center_reviewer_decision_board_quorum, unified_command_center_reviewer_decision_board_evidence_review_zip_path, unified_command_center_reviewer_decision_board_evidence_review_verification_report_path, unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths, unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths, unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths, require_unified_release_program_handoff, unified_release_program_handoff_zip_path, unified_release_program_handoff_verification_report_path, unified_release_program_handoff_external_evidence_manifest_path, unified_release_program_handoff_signoff_binding_path, require_unified_release_program_vault, unified_release_program_vault_zip_path, unified_release_program_vault_verification_report_path, unified_release_program_vault_anchor_path, require_unified_release_program_vault_operations, unified_release_program_vault_operations_zip_path, unified_release_program_vault_operations_verification_report_path, unified_release_program_vault_operations_signoff_binding_path, require_unified_release_program_continuity, unified_release_program_continuity_zip_path, unified_release_program_continuity_verification_report_path, unified_release_program_continuity_signoff_binding_path, require_unified_release_program_continuity_kit, unified_release_program_continuity_kit_zip_path, unified_release_program_continuity_kit_verification_report_path, unified_release_program_continuity_kit_receiver_receipt_path, require_unified_release_program_continuity_acceptance, unified_release_program_continuity_acceptance_zip_path, unified_release_program_continuity_acceptance_verification_report_path, unified_release_program_continuity_acceptance_signoff_binding_path, require_unified_release_program_continuity_command_center, unified_release_program_continuity_command_center_zip_path, unified_release_program_continuity_command_center_verification_report_path, unified_release_program_continuity_command_center_external_evidence_manifest_path, require_unified_release_program_continuity_command_center_signoff, unified_release_program_continuity_command_center_signoff_archive_path, unified_release_program_continuity_command_center_signoff_verification_report_path, unified_release_program_continuity_command_center_signoff_binding_path, require_unified_release_program_continuity_command_center_acceptance, unified_release_program_continuity_command_center_acceptance_archive_path, unified_release_program_continuity_command_center_acceptance_verification_report_path, unified_release_program_continuity_command_center_acceptance_signoff_binding_path, unified_release_program_continuity_command_center_acceptance_review_pack_path, unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path, unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir, unified_release_program_continuity_command_center_acceptance_response_proof_dir, require_unified_release_program_continuity_command_center_acceptance_change_control, unified_release_program_continuity_command_center_acceptance_change_archive_path, unified_release_program_continuity_command_center_acceptance_change_verification_report_path, unified_release_program_continuity_command_center_acceptance_previous_root, unified_release_program_continuity_command_center_final_handoff_path, unified_release_program_continuity_command_center_final_handoff_verification_report_path, unified_release_zip_path, unified_release_verification_report_path, unified_distribution_zip_paths, unified_distribution_verification_report_paths, unified_submission_zip_paths, unified_submission_verification_report_paths, unified_release_operations_zip_path, unified_release_operations_verification_report_path, unified_trust_operations_hub_zip_path, unified_trust_operations_hub_verification_report_path, unified_public_trust_center_zip_path, unified_public_trust_center_verification_report_path, unified_maintenance_backup_zip_path, unified_maintenance_backup_verification_report_path, require_final_readiness, final_handoff_verification_report_path, release_check_latest_report_path, release_check_ga_report_path, run_release_checks, skip_tests, release_check_executor, _split_state)
    if _split_result[0]:
        return _split_result[1]


def _evidence_policy_summary(policy: str | None, evidence_manifest_path: Path | str | None) -> ImplementationDocument:
    effective_policy = policy or ("ga.standard" if evidence_manifest_path else None)
    if not effective_policy:
        return {"status": "not_requested", "policy_id": None}
    if evidence_manifest_path is None:
        return {
            "status": "failed",
            "policy_id": effective_policy,
            "blockers": ["ga_policy_evidence_manifest_required"],
            "message": "Policy evaluation requires an external evidence manifest.",
        }
    try:
        from song_agent.platform.evidence_graph import build_evidence_graph
        from song_agent.platform.policy import evaluate_policy, get_policy_profile
        from song_agent.platform.verification.hashing import integrity_ok
        from song_agent.capabilities import capability_registry

        manifest = read_json(Path(evidence_manifest_path))
        graph = build_evidence_graph(evidence_manifest_path, registry=capability_registry)
        gate = evaluate_policy(get_policy_profile(effective_policy), graph)
        return {
            "status": gate.status,
            "policy_id": gate.policy_id,
            "graph_hash": gate.graph_hash,
            "manifest_hash": manifest.get("integrity_hash") if integrity_ok(manifest) else None,
            "blockers": list(gate.blockers),
            "warnings": list(gate.warnings),
            "checks": list(gate.checks),
            "graph": graph.to_dict(),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "policy_id": effective_policy,
            "blockers": ["ga_policy_evaluation_error"],
            "message": str(exc),
        }








def write_ga_readiness_report(report: dict[str, Any], path: Path | str = DEFAULT_GA_REPORT_PATH) -> Path:
    target = Path(path)
    write_json(target, sanitize_ga_report(report))
    return target


def read_ga_readiness_report(path: Path | str = DEFAULT_GA_REPORT_PATH, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"GA readiness report not found: {target}")
    return sanitize_ga_report(read_json(target))


def sanitize_ga_report(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_ga_report(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_ga_report(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _add_check(checks: list[ImplementationDocument], check_id: str, status: str, severity: str, message: str, detail: ImplementationDocument | None = None) -> None:
    checks.append(
        sanitize_ga_report(
            {
                "check_id": check_id,
                "status": status,
                "severity": severity,
                "message": message,
                "detail": detail or {},
            }
        )
    )


def _version_summary(root: Path) -> ImplementationDocument:
    pyproject_version = "unknown"
    try:
        with (root / "pyproject.toml").open("rb") as file:
            pyproject_version = str((tomllib.load(file).get("project") or {}).get("version") or "unknown")
    except Exception:
        pyproject_version = "unknown"
    return {
        "package_version": __version__,
        "pyproject_version": pyproject_version,
        "consistent": __version__ == pyproject_version and pyproject_version != "unknown",
    }


def _git_summary(root: Path) -> ImplementationDocument:
    try:
        status = subprocess.run(["git", "status", "--short", "--branch"], cwd=root, text=True, capture_output=True, timeout=20)
        lines = [line for line in status.stdout.splitlines() if line.strip()]
        branch = lines[0] if lines else ""
        dirty = any(not line.startswith("## ") for line in lines)
        ahead = "ahead" in branch
        behind = "behind" in branch
        state = "dirty" if dirty else "ahead" if ahead else "behind" if behind else "clean"
        return {"state": state, "branch": branch, "dirty": dirty, "ahead": ahead, "behind": behind}
    except Exception as exc:
        return {"state": "unknown", "error": str(exc)}


def _doctor_summary(root: Path) -> ImplementationDocument:
    cwd_writable = _writable(root)
    runs_writable = _writable(root / "runs")
    status = "passed" if cwd_writable and runs_writable else "failed"
    return {
        "status": status,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "cwd_writable": cwd_writable,
        "runs_writable": runs_writable,
        "deterministic_mode": "ok",
    }


def _docs_summary(root: Path) -> ImplementationDocument:
    present = []
    missing = []
    for rel in REQUIRED_DOCS:
        (present if (root / rel).exists() else missing).append(rel)
    return {"present": present, "missing": missing, "required_count": len(REQUIRED_DOCS)}


def _secret_summary(root: Path) -> ImplementationDocument:
    findings: list[dict[str, Any]] = []
    for rel in ("README.md", "CHANGELOG.md", *REQUIRED_DOCS):
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                findings.append({"path": rel, "pattern": pattern.pattern})
    return {"findings": findings, "scanned": ["README.md", "CHANGELOG.md", *REQUIRED_DOCS]}


def _renderer_summary(root: Path) -> ImplementationDocument:
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        store = AudioProfileStore(root / ".musicforge" / "audio-profiles")
        try:
            profile = store.get_profile()
        except AudioProfileNotFoundError:
            return {"status": "missing", "profile_id": None}
        return {
            "status": "configured",
            "profile_id": profile.profile_id,
            "engine": profile.engine,
            "enabled": profile.enabled,
            "soundfont_configured": bool(profile.soundfont_path),
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        os.chdir(previous_cwd)


def _provider_summary(root: Path) -> ImplementationDocument:
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        config, _sources = load_provider_config()
        if provider_configured(config):
            status = "mock" if str(config.wire_api).lower() == "mock" else "configured"
        elif config.model or config.base_url or config.api_key:
            status = "incomplete"
        else:
            status = "missing"
        return {"status": status, "wire_api": config.wire_api or "", "model": config.model or ""}
    except ProviderError as exc:
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        return {"status": "unknown", "error": str(exc)}
    finally:
        os.chdir(previous_cwd)


def _acceptance_summary(root: Path) -> ImplementationDocument:
    store = AcceptanceStore(root=root / ".musicforge" / "acceptance")
    candidates: list[dict[str, Any]] = []
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
) -> ImplementationDocument:
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
) -> ImplementationDocument:
    if remediation_zip_path is None:
        return {"status": "missing", "message": "Audio Campaign remediation package was not provided."}
    try:
        zip_path = Path(remediation_zip_path)
        runtime_report = verify_audio_campaign_remediation_package(zip_path, strict=True, require_passed=required, require_signed=False)
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
        if certification_verification_report_path is not None:
            external_report = read_json(Path(certification_verification_report_path))
        summary = runtime_report.get("summary") if isinstance(runtime_report.get("summary"), dict) else {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
        if timeline_verification_report_path is not None:
            external_report = read_json(Path(timeline_verification_report_path))
        summary = runtime_report.get("summary") if isinstance(runtime_report.get("summary"), dict) else {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
        if regression_verification_report_path is not None:
            external_report = read_json(Path(regression_verification_report_path))
        summary = runtime_report.get("summary") if isinstance(runtime_report.get("summary"), dict) else {}
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
) -> ImplementationDocument:
    if registry_zip_path is None:
        return {"status": "missing", "message": "Release Audio Baseline Registry package was not provided."}
    try:
        zip_path = Path(registry_zip_path)
        runtime_report = verify_release_audio_baseline_registry_package(zip_path, strict=True, require_active=required)
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
            **current_args,
        )
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
    if command_center_zip_path is None:
        return {"status": "missing", "message": "Unified Command Center package was not provided."}
    try:
        from song_agent.domains.program.unified_command_center import evidence_to_verifier_kwargs as unified_command_center_evidence_to_kwargs
        from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package

        zip_path = Path(command_center_zip_path)
        evidence: dict[str, Any] = {
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
        if review_verification_report_path is not None:
            external_report = read_json(Path(review_verification_report_path))
        external_fp = _verification_fingerprint(external_report) if external_report else {}
        runtime_fp = _verification_fingerprint(runtime_report)
        from song_agent.domains.delivery.releases import stable_hash as release_stable_hash

        external_integrity_ok = not external_report or external_report.get("integrity_hash") == release_stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
        zip_binding_ok = not external_report or external_fp.get("zip_sha256") == runtime_fp.get("zip_sha256")
        manifest_binding_ok = not external_report or external_fp.get("manifest_hash") == runtime_fp.get("manifest_hash")
        status = "passed" if runtime_report.get("status") == "passed" and (not external_report or external_report.get("status") == "passed") and external_integrity_ok and zip_binding_ok and manifest_binding_ok else "failed"
        acceptance_summary: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
            accepted_evidence_paths=accepted_evidence_zip_paths or [],
            accepted_evidence_verification_report_paths=accepted_evidence_verification_report_paths or [],
            accepted_evidence_response_verification_report_paths=accepted_evidence_response_verification_report_paths or [],
        )
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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


def _unified_release_program_continuity_acceptance_summary(
    *,
    required: bool,
    archive_zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    kit_zip_path: Path | str | None,
    kit_verification_report_path: Path | str | None,
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
        external_report: dict[str, Any] = {}
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
) -> ImplementationDocument:
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
) -> ImplementationDocument:
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
) -> ImplementationDocument:
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


def _verification_fingerprint(report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
    }


def _acceptance_check_status(summary: ImplementationDocument, *, require_manual_acceptance: bool, require_audio: bool) -> dict[str, str]:
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
    executor: Callable[..., Any] | None,
) -> ImplementationDocument:
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


def _final_readiness_summary(path: Path | str | None) -> ImplementationDocument:
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


def _next_actions(checks: list[ImplementationDocument]) -> list[dict[str, str]]:
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


def _redact_text(value: str) -> str:
    text = value
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-...redacted", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_...redacted", text)
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_...redacted", text)
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\n]+", r"C:\\Users\\<user>", text)
    return text
