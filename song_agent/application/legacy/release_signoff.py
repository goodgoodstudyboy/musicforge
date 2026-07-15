from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from song_agent.application.policy_compatibility import evaluate_legacy_release_policy

from song_agent.domains.quality.audio_encoding import encoded_audio_gate, normalize_required_profiles

from song_agent.application.legacy_dependencies.release_export import (
    build_release_export_zip,
    read_release_export_manifest,
    refresh_release_export_signoff_summary,
)

from song_agent.application.legacy_dependencies.release_qa import (
    build_release_signoff_record,
    release_qa_allows_signoff,
    release_signoff_summary,
)

from song_agent.application.legacy_dependencies.releases import stable_hash

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class LegacyReleaseSignoffAdapter:
    def __init__(self, port: object) -> None:
        self.port = port

    def __getattr__(self, name: str) -> Any:
        return getattr(self.port, name)

    def execute(self, method: str, release_id: str) -> None:
        if method == "GET":
            signoff = self.release_store.read_signoff(release_id, default={})
            self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": release_signoff_summary(signoff)})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        existing = self.release_store.read_signoff(release_id, default={})
        if existing:
            self._send_error(HTTPStatus.CONFLICT, "Release is already signed off. Reset signoff before signing again.")
            return
        document = self.release_store.get_release(release_id)
        report = self._get_or_refresh_release_qa(release_id, refresh=True, options={})
        force = bool(payload.get("force", False))
        acceptance_gate = self._release_acceptance_gate({**payload, "release_id": release_id, "force": force})
        policy_gate = self._release_declarative_policy_gate(payload)
        if policy_gate:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["evidence_policy"] = policy_gate
            if policy_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(policy_gate.get("message") or "Release Evidence Graph policy failed.")
        audio_gate = self._release_audio_gate(release_id, payload)
        if audio_gate:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio"] = audio_gate
            if audio_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_gate.get("message") or "Release audio gate failed.")
        require_mastering_qa = bool(payload.get("require_mastering_qa", False))
        mastering_gate = self.mastering_store.gate(
            release_id,
            required=require_mastering_qa,
            profile_id=str(payload.get("mastering_profile_id") or "") or None,
            force=force,
        )
        if mastering_gate and require_mastering_qa:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["mastering"] = mastering_gate
            if mastering_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(mastering_gate.get("message") or "Mastering QA gate failed.")
        require_encoded_audio = bool(payload.get("require_encoded_audio", False))
        required_encoded_profiles = normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("audio_format_profiles") or [])
        encoded_gate = encoded_audio_gate(
            self.audio_encoding_store,
            release_id,
            required_profiles=required_encoded_profiles,
            required=require_encoded_audio,
            force=force,
        )
        if encoded_gate and require_encoded_audio:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["encoded_audio"] = encoded_gate
            if encoded_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(encoded_gate.get("message") or "Encoded audio gate failed.")
        require_encoded_audio_review = bool(payload.get("require_encoded_audio_review", False))
        encoded_acceptance_gate = self.encoded_audio_acceptance_store.gate(
            release_id,
            required_profiles=required_encoded_profiles,
            required=require_encoded_audio_review,
            now=_utc_now(),
        )
        if encoded_acceptance_gate and require_encoded_audio_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["encoded_audio_acceptance"] = encoded_acceptance_gate
            if encoded_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(encoded_acceptance_gate.get("message") or "Encoded audio acceptance gate failed.")
        require_format_decision = bool(payload.get("require_format_decision", False))
        format_decision_gate = self.format_decision_store.gate(
            release_id,
            required=require_format_decision,
            session_id=str(payload.get("format_decision_session_id") or "") or None,
            required_profiles=required_encoded_profiles,
        )
        if format_decision_gate and require_format_decision:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["format_decision"] = format_decision_gate
            if format_decision_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(format_decision_gate.get("message") or "Format decision gate failed.")
        require_rights_clearance = bool(payload.get("require_rights_clearance", False))
        rights_gate = self.rights_clearance_store.gate(release_id, required=require_rights_clearance, now=_utc_now())
        if rights_gate and require_rights_clearance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["rights_clearance"] = rights_gate
            if rights_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(rights_gate.get("message") or "Rights clearance gate failed.")
        require_audio_campaign = bool(payload.get("require_audio_campaign", False))
        audio_campaign_gate = self._release_audio_campaign_gate(release_id, payload, required=require_audio_campaign)
        if audio_campaign_gate and require_audio_campaign:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio_campaign"] = audio_campaign_gate
            if audio_campaign_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_campaign_gate.get("message") or "Audio Campaign gate failed.")
        require_audio_campaign_remediation = bool(payload.get("require_audio_campaign_remediation", False))
        audio_campaign_remediation_gate = self.audio_campaign_remediation_store.gate(release_id, required=require_audio_campaign_remediation, require_signed=bool(payload.get("require_audio_campaign_remediation_signed", False)))
        if audio_campaign_remediation_gate and require_audio_campaign_remediation:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio_campaign_remediation"] = audio_campaign_remediation_gate
            if audio_campaign_remediation_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_campaign_remediation_gate.get("message") or "Audio Campaign remediation gate failed.")
        require_release_audio_certification = bool(payload.get("require_release_audio_certification", False))
        release_audio_certification_gate = self.release_audio_certification_store.gate(
            release_id,
            required=require_release_audio_certification,
            require_signed=bool(payload.get("require_release_audio_certification_signed", require_release_audio_certification)),
        )
        if release_audio_certification_gate and require_release_audio_certification:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_certification"] = release_audio_certification_gate
            if release_audio_certification_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_certification_gate.get("message") or "Release Audio Certification gate failed.")
        require_release_audio_timeline = bool(payload.get("require_release_audio_timeline", False))
        release_audio_timeline_gate = self.release_audio_timeline_store.gate(
            release_id,
            required=require_release_audio_timeline,
            require_signed=bool(payload.get("require_release_audio_timeline_signed", require_release_audio_timeline)),
            require_current_certification=bool(payload.get("require_release_audio_timeline_current_certification", True)),
        )
        if release_audio_timeline_gate and require_release_audio_timeline:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_timeline"] = release_audio_timeline_gate
            if release_audio_timeline_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_timeline_gate.get("message") or "Release Audio Timeline gate failed.")
        require_release_audio_regression = bool(payload.get("require_release_audio_regression_guard", False))
        release_audio_regression_gate = self.release_audio_regression_store.gate(
            release_id,
            required=require_release_audio_regression,
            require_signed=bool(payload.get("require_release_audio_regression_signed", require_release_audio_regression)),
        )
        if release_audio_regression_gate and require_release_audio_regression:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_regression_guard"] = release_audio_regression_gate
            if release_audio_regression_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_regression_gate.get("message") or "Release Audio Regression gate failed.")
        require_release_audio_baseline_governance = bool(payload.get("require_release_audio_baseline_governance", False))
        release_audio_baseline_governance_gate = self.release_audio_baseline_governance_store.gate(
            release_id,
            baseline_id=payload.get("release_audio_baseline_id"),
            required=require_release_audio_baseline_governance,
        )
        if release_audio_baseline_governance_gate and require_release_audio_baseline_governance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_baseline_governance"] = release_audio_baseline_governance_gate
            if release_audio_baseline_governance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_baseline_governance_gate.get("message") or "Release Audio Baseline Governance gate failed.")
        require_release_audio_regression_response = bool(payload.get("require_release_audio_regression_response", False))
        release_audio_regression_response_gate = self.release_audio_regression_response_store.gate(
            release_id,
            required=require_release_audio_regression_response,
            require_signed=bool(payload.get("require_release_audio_regression_response_signed", require_release_audio_regression_response)),
        )
        if release_audio_regression_response_gate and require_release_audio_regression_response:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_regression_response"] = release_audio_regression_response_gate
            if release_audio_regression_response_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_regression_response_gate.get("message") or "Release Audio Regression Response gate failed.")
        require_release_audio_quality_observatory = bool(payload.get("require_release_audio_quality_observatory", False))
        release_audio_quality_observatory_gate = self.release_audio_quality_observatory_store.gate(
            release_id,
            observatory_id=payload.get("release_audio_quality_observatory_id"),
            required=require_release_audio_quality_observatory,
            require_no_critical_risk=bool(payload.get("require_no_critical_audio_quality_risk", require_release_audio_quality_observatory)),
        )
        if release_audio_quality_observatory_gate and require_release_audio_quality_observatory:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_observatory"] = release_audio_quality_observatory_gate
            if release_audio_quality_observatory_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_observatory_gate.get("message") or "Release Audio Quality Observatory gate failed.")
        require_release_audio_quality_action_queue = bool(payload.get("require_release_audio_quality_action_queue", False))
        release_audio_quality_action_queue_gate = self.release_audio_quality_action_queue_store.gate(
            release_id,
            queue_id=payload.get("release_audio_quality_action_queue_id"),
            required=require_release_audio_quality_action_queue,
            require_no_blocking=bool(payload.get("require_no_blocking_audio_quality_action", True)),
        )
        if release_audio_quality_action_queue_gate and require_release_audio_quality_action_queue:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_action_queue"] = release_audio_quality_action_queue_gate
            if release_audio_quality_action_queue_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_action_queue_gate.get("message") or "Release Audio Quality Action Queue gate failed.")
        require_release_audio_quality_action_queue_signoff = bool(payload.get("require_release_audio_quality_action_queue_signoff", False))
        release_audio_quality_action_queue_signoff_gate = self.release_audio_quality_action_signoff_store.gate(
            release_id,
            queue_id=payload.get("release_audio_quality_action_queue_id") or payload.get("release_audio_quality_action_queue_signoff_id"),
            required=require_release_audio_quality_action_queue_signoff,
        )
        if release_audio_quality_action_queue_signoff_gate and require_release_audio_quality_action_queue_signoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_action_queue_signoff"] = release_audio_quality_action_queue_signoff_gate
            if release_audio_quality_action_queue_signoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_action_queue_signoff_gate.get("message") or "Release Audio Quality Action Queue signoff gate failed.")
        require_release_audio_command_center = bool(payload.get("require_release_audio_command_center", False))
        release_audio_command_center_gate = self.release_audio_command_center_store.gate(
            release_id,
            required=require_release_audio_command_center,
            command_center_zip_path=payload.get("release_audio_command_center_zip") or payload.get("release_audio_command_center"),
            command_center_verification_report_path=payload.get("release_audio_command_center_verification_report"),
            evidence={
                "certification": {"zip": payload.get("release_audio_certification_zip"), "verification_report": payload.get("release_audio_certification_verification_report")},
                "timeline": {"zip": payload.get("release_audio_timeline_zip"), "verification_report": payload.get("release_audio_timeline_verification_report")},
                "regression": {"zip": payload.get("release_audio_regression_zip"), "verification_report": payload.get("release_audio_regression_verification_report")},
                "baseline_governance": {"zip": payload.get("release_audio_baseline_registry_zip"), "verification_report": payload.get("release_audio_baseline_registry_verification_report")},
                "regression_response": {"zip": payload.get("release_audio_regression_response_zip"), "verification_report": payload.get("release_audio_regression_response_verification_report")},
                "observatory": {"zip": payload.get("release_audio_quality_observatory_zip"), "verification_report": payload.get("release_audio_quality_observatory_verification_report")},
                "action_queue": {"zip": payload.get("release_audio_quality_action_queue_zip"), "verification_report": payload.get("release_audio_quality_action_queue_verification_report")},
                "action_queue_signoff": {"zip": payload.get("release_audio_quality_action_queue_signoff_archive"), "verification_report": payload.get("release_audio_quality_action_queue_signoff_verification_report")},
                "evidence_root": payload.get("release_audio_quality_observatory_evidence_root"),
            },
        )
        if release_audio_command_center_gate and require_release_audio_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_command_center"] = release_audio_command_center_gate
            if release_audio_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_command_center_gate.get("message") or "Release Audio Command Center gate failed.")
        require_unified_command_center = bool(payload.get("require_unified_command_center", False))
        unified_command_center_gate = self.unified_command_center_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center,
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            evidence={
                "audio-command-center": {"zip": payload.get("release_audio_command_center_zip") or payload.get("release_audio_command_center"), "verification_report": payload.get("release_audio_command_center_verification_report")},
                "ga-readiness": {"report": payload.get("ga_readiness_report")},
                "release-check": {"report": payload.get("release_check_report")},
                "requirements": {"require_audio_command_center": bool(payload.get("require_release_audio_command_center", False))},
            },
        )
        if unified_command_center_gate and require_unified_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center"] = unified_command_center_gate
            if unified_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_gate.get("message") or "Unified Command Center gate failed.")
        require_unified_command_center_archive = bool(payload.get("require_unified_command_center_archive", False))
        unified_command_center_archive_gate = self.unified_command_center_signoff_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_archive,
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
        )
        if unified_command_center_archive_gate and require_unified_command_center_archive:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_archive"] = unified_command_center_archive_gate
            if unified_command_center_archive_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_archive_gate.get("message") or "Unified Command Center Archive gate failed.")
        require_unified_command_center_handoff = bool(payload.get("require_unified_command_center_handoff", False))
        unified_command_center_handoff_gate = self.unified_command_center_handoff_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_handoff,
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
        )
        if unified_command_center_handoff_gate and require_unified_command_center_handoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_handoff"] = unified_command_center_handoff_gate
            if unified_command_center_handoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_handoff_gate.get("message") or "Unified Command Center Handoff gate failed.")
        require_unified_command_center_continuous_review = bool(payload.get("require_unified_command_center_continuous_review", False))
        unified_command_center_continuous_review_gate = self.unified_command_center_continuous_review_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_continuous_review,
            review_id=payload.get("unified_command_center_continuous_review_id"),
            review_zip_path=payload.get("unified_command_center_continuous_review") or payload.get("unified_command_center_continuous_review_zip"),
            review_verification_report_path=payload.get("unified_command_center_continuous_review_verification_report"),
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            signoff_binding_path=payload.get("unified_command_center_signoff_binding"),
        )
        if unified_command_center_continuous_review_gate and require_unified_command_center_continuous_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_continuous_review"] = unified_command_center_continuous_review_gate
            if unified_command_center_continuous_review_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_continuous_review_gate.get("message") or "Unified Command Center Continuous Review gate failed.")
        require_unified_command_center_drift_response = bool(payload.get("require_unified_command_center_drift_response", False))
        unified_command_center_drift_response_gate = self.unified_command_center_drift_response_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_drift_response,
            response_id=payload.get("unified_command_center_drift_response_id"),
            response_zip_path=payload.get("unified_command_center_drift_response") or payload.get("unified_command_center_drift_response_zip"),
            response_verification_report_path=payload.get("unified_command_center_drift_response_verification_report"),
            source_review_zip_path=payload.get("unified_command_center_drift_source_review") or payload.get("unified_command_center_drift_source_review_zip"),
            source_review_verification_report_path=payload.get("unified_command_center_drift_source_review_verification_report"),
            recheck_review_zip_path=payload.get("unified_command_center_drift_recheck_review") or payload.get("unified_command_center_drift_recheck_review_zip"),
            recheck_review_verification_report_path=payload.get("unified_command_center_drift_recheck_review_verification_report"),
            change_request_binding_report_path=payload.get("unified_command_center_drift_change_request_binding_report"),
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            signoff_binding_path=payload.get("unified_command_center_signoff_binding"),
        )
        if unified_command_center_drift_response_gate and require_unified_command_center_drift_response:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_drift_response"] = unified_command_center_drift_response_gate
            if unified_command_center_drift_response_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_drift_response_gate.get("message") or "Unified Command Center Drift Response gate failed.")
        require_unified_command_center_evidence_review = bool(payload.get("require_unified_command_center_evidence_review", False))
        unified_command_center_evidence_review_gate = self.unified_command_center_evidence_review_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_evidence_review,
            review_id=payload.get("unified_command_center_evidence_review_id"),
            review_zip_path=payload.get("unified_command_center_evidence_review") or payload.get("unified_command_center_evidence_review_zip"),
            review_verification_report_path=payload.get("unified_command_center_evidence_review_verification_report"),
            require_accepted=bool(payload.get("require_unified_command_center_evidence_review_accepted", False)),
            acceptance_zip_path=payload.get("unified_command_center_evidence_review_acceptance") or payload.get("unified_command_center_evidence_review_acceptance_zip"),
            acceptance_verification_report_path=payload.get("unified_command_center_evidence_review_acceptance_verification_report"),
            acceptance_response_verification_report_path=payload.get("unified_command_center_evidence_review_acceptance_response_verification_report"),
            payload=payload,
        )
        if unified_command_center_evidence_review_gate and require_unified_command_center_evidence_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_evidence_review"] = unified_command_center_evidence_review_gate
            if unified_command_center_evidence_review_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_evidence_review_gate.get("message") or "Unified Command Center Evidence Review gate failed.")
        require_unified_command_center_reviewer_decision_board = bool(payload.get("require_unified_command_center_reviewer_decision_board", False))
        unified_command_center_reviewer_decision_board_gate = self.unified_command_center_reviewer_decision_board_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_reviewer_decision_board,
            board_id=payload.get("unified_command_center_reviewer_decision_board_id"),
            archive_zip_path=payload.get("unified_command_center_reviewer_decision_board_archive") or payload.get("unified_command_center_reviewer_decision_board_zip"),
            verification_report_path=payload.get("unified_command_center_reviewer_decision_board_verification_report"),
            require_signed=bool(payload.get("require_unified_command_center_reviewer_decision_board_signed", True)),
            require_quorum=bool(payload.get("require_unified_command_center_reviewer_decision_board_quorum", True)),
            payload=payload,
        )
        if unified_command_center_reviewer_decision_board_gate and require_unified_command_center_reviewer_decision_board:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_reviewer_decision_board"] = unified_command_center_reviewer_decision_board_gate
            if unified_command_center_reviewer_decision_board_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_reviewer_decision_board_gate.get("message") or "Unified Command Center Reviewer Decision Board gate failed.")
        require_unified_command_center_release_train = bool(payload.get("require_unified_command_center_release_train", False))
        unified_command_center_release_train_gate = self.unified_command_center_release_train_store.gate(
            str(payload.get("unified_command_center_release_train_id") or "uct-000001"),
            required=require_unified_command_center_release_train,
            archive_zip_path=payload.get("unified_command_center_release_train_archive") or payload.get("unified_command_center_release_train_zip"),
            verification_report_path=payload.get("unified_command_center_release_train_verification_report"),
            external_evidence_manifest_path=payload.get("unified_command_center_release_train_external_evidence_manifest"),
            signoff_binding_path=payload.get("unified_command_center_release_train_signoff_binding"),
        )
        if unified_command_center_release_train_gate and require_unified_command_center_release_train:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_release_train"] = unified_command_center_release_train_gate
            if unified_command_center_release_train_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_release_train_gate.get("message") or "Unified Command Center Release Train gate failed.")
        require_unified_release_program_handoff = bool(payload.get("require_unified_release_program_handoff", False))
        unified_release_program_handoff_gate = self.unified_release_program_handoff_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_handoff_program_id") or "urp-000001"),
            required=require_unified_release_program_handoff,
            handoff_archive_zip_path=payload.get("unified_release_program_handoff_archive") or payload.get("unified_release_program_handoff_zip"),
            handoff_archive_verification_report_path=payload.get("unified_release_program_handoff_verification_report"),
            external_evidence_manifest=payload.get("unified_release_program_handoff_external_evidence_manifest"),
            handoff_signoff_binding=payload.get("unified_release_program_handoff_signoff_binding"),
        )
        if unified_release_program_handoff_gate and require_unified_release_program_handoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_handoff"] = unified_release_program_handoff_gate
            if unified_release_program_handoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_handoff_gate.get("message") or "Unified Release Program Handoff gate failed.")
        require_unified_release_program_vault = bool(payload.get("require_unified_release_program_vault", False))
        unified_release_program_vault_gate = self.unified_release_program_vault_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_vault_program_id") or "urp-000001"),
            required=require_unified_release_program_vault,
            vault_zip_path=payload.get("unified_release_program_vault") or payload.get("unified_release_program_vault_zip"),
            vault_verification_report_path=payload.get("unified_release_program_vault_verification_report"),
            vault_anchor_path=payload.get("unified_release_program_vault_anchor"),
            require_current_program=bool(payload.get("unified_release_program_vault_require_current_program", False)),
            require_current_operations=bool(payload.get("unified_release_program_vault_require_current_operations", False)),
            require_current_handoff=bool(payload.get("unified_release_program_vault_require_current_handoff", False)),
            require_accepted_evidence=bool(payload.get("unified_release_program_vault_require_accepted_evidence", True)),
        )
        if unified_release_program_vault_gate and require_unified_release_program_vault:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_vault"] = unified_release_program_vault_gate
            if unified_release_program_vault_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_vault_gate.get("message") or "Unified Release Program Evidence Vault gate failed.")
        require_unified_release_program_vault_operations = bool(payload.get("require_unified_release_program_vault_operations", False))
        unified_release_program_vault_operations_gate = self.unified_release_program_vault_operations_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_vault_operations_program_id") or "urp-000001"),
            required=require_unified_release_program_vault_operations,
            archive_zip_path=payload.get("unified_release_program_vault_operations") or payload.get("unified_release_program_vault_operations_archive"),
            verification_report_path=payload.get("unified_release_program_vault_operations_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_vault_operations_signoff_binding"),
        )
        if unified_release_program_vault_operations_gate and require_unified_release_program_vault_operations:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_vault_operations"] = unified_release_program_vault_operations_gate
            if unified_release_program_vault_operations_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_vault_operations_gate.get("message") or "Unified Release Program Vault Operations gate failed.")
        require_unified_release_program_continuity = bool(payload.get("require_unified_release_program_continuity", False))
        unified_release_program_continuity_gate = self.unified_release_program_continuity_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity,
            archive_zip_path=payload.get("unified_release_program_continuity") or payload.get("unified_release_program_continuity_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_continuity_signoff_binding"),
            vault_operations_archive_path=payload.get("unified_release_program_vault_operations") or payload.get("unified_release_program_vault_operations_archive"),
            vault_operations_verification_report_path=payload.get("unified_release_program_vault_operations_verification_report"),
            vault_operations_signoff_binding_path=payload.get("unified_release_program_vault_operations_signoff_binding"),
        )
        if unified_release_program_continuity_gate and require_unified_release_program_continuity:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity"] = unified_release_program_continuity_gate
            if unified_release_program_continuity_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_gate.get("message") or "Unified Release Program Continuity gate failed.")
        require_unified_release_program_continuity_kit = bool(payload.get("require_unified_release_program_continuity_kit", False))
        unified_release_program_continuity_kit_gate = self.unified_release_program_continuity_distribution_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_kit_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_kit,
            kit_zip_path=payload.get("unified_release_program_continuity_kit") or payload.get("unified_release_program_continuity_kit_zip"),
            verification_report_path=payload.get("unified_release_program_continuity_kit_verification_report"),
            receiver_receipt_path=payload.get("unified_release_program_continuity_kit_receiver_receipt"),
            require_receiver_receipt=bool(payload.get("require_unified_release_program_continuity_kit_receiver_receipt", False)),
        )
        if unified_release_program_continuity_kit_gate and require_unified_release_program_continuity_kit:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_kit"] = unified_release_program_continuity_kit_gate
            if unified_release_program_continuity_kit_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_kit_gate.get("message") or "Unified Release Program Continuity Distribution Kit gate failed.")
        require_unified_release_program_continuity_acceptance = bool(payload.get("require_unified_release_program_continuity_acceptance", False))
        unified_release_program_continuity_acceptance_gate = self.unified_release_program_continuity_acceptance_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_acceptance_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_acceptance,
            archive_zip_path=payload.get("unified_release_program_continuity_acceptance") or payload.get("unified_release_program_continuity_acceptance_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_acceptance_verification_report"),
            continuity_kit=payload.get("unified_release_program_continuity_kit") or payload.get("unified_release_program_continuity_kit_zip"),
            continuity_kit_verification_report=payload.get("unified_release_program_continuity_kit_verification_report"),
            signoff_binding=payload.get("unified_release_program_continuity_acceptance_signoff_binding"),
        )
        if unified_release_program_continuity_acceptance_gate and require_unified_release_program_continuity_acceptance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_acceptance"] = unified_release_program_continuity_acceptance_gate
            if unified_release_program_continuity_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_acceptance_gate.get("message") or "Unified Release Program Continuity Acceptance gate failed.")
        require_unified_release_program_continuity_command_center = bool(payload.get("require_unified_release_program_continuity_command_center", False))
        unified_release_program_continuity_command_center_gate = self.unified_release_program_continuity_command_center_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center,
            command_center_zip_path=payload.get("unified_release_program_continuity_command_center") or payload.get("unified_release_program_continuity_command_center_zip"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_verification_report"),
            evidence_manifest_path=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_gate and require_unified_release_program_continuity_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center"] = unified_release_program_continuity_command_center_gate
            if unified_release_program_continuity_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_gate.get("message") or "Unified Release Program Continuity Command Center gate failed.")
        require_unified_release_program_continuity_command_center_signoff = bool(payload.get("require_unified_release_program_continuity_command_center_signoff", False))
        unified_release_program_continuity_command_center_signoff_gate = self.unified_release_program_continuity_command_center_signoff_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center_signoff,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            archive_verification_report_path=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center_zip_path=payload.get("unified_release_program_continuity_command_center") or payload.get("unified_release_program_continuity_command_center_zip"),
            command_center_verification_report_path=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_external_evidence_manifest_path=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_signoff_gate and require_unified_release_program_continuity_command_center_signoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_signoff"] = unified_release_program_continuity_command_center_signoff_gate
            if unified_release_program_continuity_command_center_signoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_signoff_gate.get("message") or "Unified Release Program Continuity Command Center signoff gate failed.")
        require_unified_release_program_continuity_command_center_acceptance = bool(payload.get("require_unified_release_program_continuity_command_center_acceptance", False))
        unified_release_program_continuity_command_center_acceptance_gate = self.unified_release_program_continuity_command_center_acceptance_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center_acceptance,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_acceptance_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_acceptance_verification_report"),
            acceptance_signoff_binding=payload.get("unified_release_program_continuity_command_center_acceptance_signoff_binding"),
            review_pack=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack"),
            review_pack_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack_verification_report"),
            accepted_evidence_dir=payload.get("unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir"),
            response_proof_dir=payload.get("unified_release_program_continuity_command_center_acceptance_response_proof_dir"),
            command_center_signoff_archive=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            command_center_signoff_archive_verification_report=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            command_center_final_handoff=payload.get("unified_release_program_continuity_command_center_final_handoff"),
            command_center_final_handoff_verification_report=payload.get("unified_release_program_continuity_command_center_final_handoff_verification_report"),
            command_center_signoff_binding=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center=payload.get("unified_release_program_continuity_command_center"),
            command_center_verification_report=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_evidence_manifest=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_acceptance_gate and require_unified_release_program_continuity_command_center_acceptance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_acceptance"] = unified_release_program_continuity_command_center_acceptance_gate
            if unified_release_program_continuity_command_center_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_acceptance_gate.get("message") or "Unified Release Program Continuity Command Center Receiver Acceptance gate failed.")
        require_receiver_acceptance_change = bool(
            payload.get("require_unified_release_program_continuity_command_center_acceptance_change_control", False)
        )
        receiver_acceptance_change_gate = self.unified_release_program_continuity_command_center_acceptance_change_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_receiver_acceptance_change,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_acceptance_change_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_acceptance_change_verification_report"),
            acceptance_archive=payload.get("unified_release_program_continuity_command_center_acceptance_archive"),
            acceptance_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_verification_report"),
            acceptance_signoff_binding=payload.get("unified_release_program_continuity_command_center_acceptance_signoff_binding"),
            previous_acceptance_root=payload.get("unified_release_program_continuity_command_center_acceptance_previous_root"),
            review_pack=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack"),
            review_pack_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack_verification_report"),
            accepted_evidence_dir=payload.get("unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir"),
            response_proof_dir=payload.get("unified_release_program_continuity_command_center_acceptance_response_proof_dir"),
            command_center_signoff_archive=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            command_center_signoff_archive_verification_report=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            command_center_final_handoff=payload.get("unified_release_program_continuity_command_center_final_handoff"),
            command_center_final_handoff_verification_report=payload.get("unified_release_program_continuity_command_center_final_handoff_verification_report"),
            command_center_signoff_binding=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center=payload.get("unified_release_program_continuity_command_center"),
            command_center_verification_report=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_evidence_manifest=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if receiver_acceptance_change_gate and require_receiver_acceptance_change:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_acceptance_change_control"] = receiver_acceptance_change_gate
            if receiver_acceptance_change_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(
                    receiver_acceptance_change_gate.get("message")
                    or "Receiver Acceptance Change Control gate failed."
                )
        policy_decision = evaluate_legacy_release_policy(
            payload,
            acceptance_gate,
            release_id=release_id,
            qa_passed=release_qa_allows_signoff(report) or force,
        )
        acceptance_gate["policy_gate"] = policy_decision
        acceptance_gate["legacy_require_summary"] = policy_decision["legacy_require_summary"]
        acceptance_gate["status"] = policy_decision["status"]
        if policy_decision["status"] != "passed":
            message = str(acceptance_gate.get("message") or "Release Evidence Policy gate failed.")
            self._send_json(
                {
                    "error": message,
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if not release_qa_allows_signoff(report) and not force:
            self._send_error(HTTPStatus.CONFLICT, "Release QA gate failed. Refresh QA or pass force=true with override_reason.")
            return
        if force and not str(payload.get("override_reason") or "").strip():
            self._send_error(HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
            return
        try:
            export_manifest = read_release_export_manifest(self.release_store, release_id)
        except FileNotFoundError:
            export_manifest = {}
        if require_mastering_qa:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            mastering_export_gate = self._release_mastering_export_gate(export_manifest, mastering_gate)
            if mastering_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["mastering_export"] = mastering_export_gate
                self._send_json(
                    {
                        "error": str(mastering_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_encoded_audio:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            encoded_export_gate = self._release_encoded_audio_export_gate(export_manifest, encoded_gate)
            if encoded_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["encoded_audio_export"] = encoded_export_gate
                self._send_json(
                    {
                        "error": str(encoded_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_encoded_audio_review:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_format_decision:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            format_decision_export_gate = self._release_format_decision_export_gate(export_manifest, format_decision_gate)
            if format_decision_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["format_decision_export"] = format_decision_export_gate
                self._send_json(
                    {
                        "error": str(format_decision_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            encoded_acceptance_export_gate = self._release_encoded_audio_acceptance_export_gate(export_manifest, encoded_acceptance_gate)
            if encoded_acceptance_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["encoded_audio_acceptance_export"] = encoded_acceptance_export_gate
                self._send_json(
                    {
                        "error": str(encoded_acceptance_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_rights_clearance:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            rights_export_gate = self._release_rights_clearance_export_gate(export_manifest, rights_gate)
            if rights_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["rights_clearance_export"] = rights_export_gate
                self._send_json(
                    {
                        "error": str(rights_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if not export_manifest and not force:
            self._send_error(HTTPStatus.CONFLICT, "Release Export has not been generated.")
            return
        if export_manifest and not force:
            if export_manifest.get("source_hash") != report.get("source_hash"):
                self._send_error(HTTPStatus.CONFLICT, "Release Export is stale. Rebuild export before signoff.")
                return
            zip_summary = export_manifest.get("zip") if isinstance(export_manifest.get("zip"), dict) else {}
            zip_path = self.release_store.zip_path(release_id)
            if bool(payload.get("require_zip", True)) and not (zip_path.exists() and zip_path.is_file() and not zip_path.is_symlink() and zip_summary.get("entry_count")):
                self._send_error(HTTPStatus.CONFLICT, "Release ZIP has not been generated.")
                return
        try:
            pending_signoff = build_release_signoff_record(release=document, report=report, payload={**payload, "force": force}, export_manifest={}, now=_utc_now())
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        if acceptance_gate:
            pending_signoff["acceptance_gate"] = acceptance_gate
        self.release_store.write_signoff(release_id, {**pending_signoff, "export_manifest_hash": None})
        try:
            final_manifest = refresh_release_export_signoff_summary(self.release_store, release_id)
            final_manifest.pop("zip", None)
            final_hash = stable_hash(final_manifest)
            signoff = {**pending_signoff, "export_manifest_hash": final_hash}
            signoff = self.release_store.write_signoff(release_id, signoff)
            refresh_release_export_signoff_summary(self.release_store, release_id)
            build_release_export_zip(self.release_store, release_id, now=_utc_now(), allow_signed=True)
        except FileNotFoundError:
            signoff = self.release_store.write_signoff(release_id, pending_signoff)
        document = self.release_store.update_signoff_summary(release_id, release_signoff_summary(signoff))
        self.release_store.append_event(release_id, "release_force_signed" if force else "release_signed", {"status": report.get("status"), "forced": force})
        self._send_json({"ok": True, "release": document.to_dict(), "signoff": signoff, "summary": release_signoff_summary(signoff)})
