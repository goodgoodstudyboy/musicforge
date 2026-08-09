from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document

from datetime import datetime, timezone
from http import HTTPStatus
from typing import cast

from song_agent.application.legacy.release_signoff_ports import (
    DocumentOperation,
    ErrorSender,
    GateStorePort,
    JsonSender,
    ReleaseSignoffCompositionPort,
    ReleaseSignoffHandlerPort,
    ReleaseStorePort,
)
from song_agent.application.policy_compatibility import evaluate_legacy_release_policy
from song_agent.domains.quality.audio_encoding import encoded_audio_gate, normalize_required_profiles

from song_agent.domains.delivery.release_export import build_release_export_zip, read_release_export_manifest, refresh_release_export_signoff_summary

from song_agent.domains.delivery.release_qa import build_release_signoff_record, release_qa_allows_signoff, release_signoff_summary

from song_agent.domains.delivery.releases import stable_hash

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LegacyReleaseSignoffAdapter:
    _get_or_refresh_release_qa: DocumentOperation
    _optional_json_body: DocumentOperation
    _release_acceptance_gate: DocumentOperation
    _release_audio_campaign_gate: DocumentOperation
    _release_audio_gate: DocumentOperation
    _release_declarative_policy_gate: DocumentOperation
    _release_encoded_audio_acceptance_export_gate: DocumentOperation
    _release_encoded_audio_export_gate: DocumentOperation
    _release_format_decision_export_gate: DocumentOperation
    _release_mastering_export_gate: DocumentOperation
    _release_rights_clearance_export_gate: DocumentOperation
    _send_error: ErrorSender
    _send_json: JsonSender
    release_store: ReleaseStorePort
    audio_campaign_remediation_store: GateStorePort
    encoded_audio_acceptance_store: GateStorePort
    format_decision_store: GateStorePort
    mastering_store: GateStorePort
    release_audio_baseline_governance_store: GateStorePort
    release_audio_certification_store: GateStorePort
    release_audio_command_center_store: GateStorePort
    release_audio_quality_action_queue_store: GateStorePort
    release_audio_quality_action_signoff_store: GateStorePort
    release_audio_quality_observatory_store: GateStorePort
    release_audio_regression_response_store: GateStorePort
    release_audio_regression_store: GateStorePort
    release_audio_timeline_store: GateStorePort
    rights_clearance_store: GateStorePort
    unified_command_center_continuous_review_store: GateStorePort
    unified_command_center_drift_response_store: GateStorePort
    unified_command_center_evidence_review_store: GateStorePort
    unified_command_center_handoff_store: GateStorePort
    unified_command_center_release_train_store: GateStorePort
    unified_command_center_reviewer_decision_board_store: GateStorePort
    unified_command_center_signoff_store: GateStorePort
    unified_command_center_store: GateStorePort
    unified_release_program_continuity_acceptance_store: GateStorePort
    unified_release_program_continuity_command_center_acceptance_change_store: GateStorePort
    unified_release_program_continuity_command_center_acceptance_store: GateStorePort
    unified_release_program_continuity_command_center_signoff_store: GateStorePort
    unified_release_program_continuity_command_center_store: GateStorePort
    unified_release_program_continuity_distribution_store: GateStorePort
    unified_release_program_continuity_store: GateStorePort
    unified_release_program_handoff_store: GateStorePort
    unified_release_program_vault_operations_store: GateStorePort
    unified_release_program_vault_store: GateStorePort
    def __init__(self, port: object) -> None:
        dependencies = cast(ReleaseSignoffHandlerPort, port)
        composition = cast(ReleaseSignoffCompositionPort, dependencies.server)
        self._get_or_refresh_release_qa = dependencies._get_or_refresh_release_qa
        self._optional_json_body = dependencies._optional_json_body
        self._release_acceptance_gate = dependencies._release_acceptance_gate
        self._release_audio_campaign_gate = dependencies._release_audio_campaign_gate
        self._release_audio_gate = dependencies._release_audio_gate
        self._release_declarative_policy_gate = dependencies._release_declarative_policy_gate
        self._release_encoded_audio_acceptance_export_gate = dependencies._release_encoded_audio_acceptance_export_gate
        self._release_encoded_audio_export_gate = dependencies._release_encoded_audio_export_gate
        self._release_format_decision_export_gate = dependencies._release_format_decision_export_gate
        self._release_mastering_export_gate = dependencies._release_mastering_export_gate
        self._release_rights_clearance_export_gate = dependencies._release_rights_clearance_export_gate
        self._send_error = dependencies._send_error
        self._send_json = dependencies._send_json
        self.audio_encoding_store = composition.audio_encoding_store
        self.release_store = composition.release_store
        self.audio_campaign_remediation_store = composition.audio_campaign_remediation_store
        self.encoded_audio_acceptance_store = composition.encoded_audio_acceptance_store
        self.format_decision_store = composition.format_decision_store
        self.mastering_store = composition.mastering_store
        self.release_audio_baseline_governance_store = composition.release_audio_baseline_governance_store
        self.release_audio_certification_store = composition.release_audio_certification_store
        self.release_audio_command_center_store = composition.release_audio_command_center_store
        self.release_audio_quality_action_queue_store = composition.release_audio_quality_action_queue_store
        self.release_audio_quality_action_signoff_store = composition.release_audio_quality_action_signoff_store
        self.release_audio_quality_observatory_store = composition.release_audio_quality_observatory_store
        self.release_audio_regression_response_store = composition.release_audio_regression_response_store
        self.release_audio_regression_store = composition.release_audio_regression_store
        self.release_audio_timeline_store = composition.release_audio_timeline_store
        self.rights_clearance_store = composition.rights_clearance_store
        self.unified_command_center_continuous_review_store = composition.unified_command_center_continuous_review_store
        self.unified_command_center_drift_response_store = composition.unified_command_center_drift_response_store
        self.unified_command_center_evidence_review_store = composition.unified_command_center_evidence_review_store
        self.unified_command_center_handoff_store = composition.unified_command_center_handoff_store
        self.unified_command_center_release_train_store = composition.unified_command_center_release_train_store
        self.unified_command_center_reviewer_decision_board_store = composition.unified_command_center_reviewer_decision_board_store
        self.unified_command_center_signoff_store = composition.unified_command_center_signoff_store
        self.unified_command_center_store = composition.unified_command_center_store
        self.unified_release_program_continuity_acceptance_store = composition.unified_release_program_continuity_acceptance_store
        self.unified_release_program_continuity_command_center_acceptance_change_store = composition.unified_release_program_continuity_command_center_acceptance_change_store
        self.unified_release_program_continuity_command_center_acceptance_store = composition.unified_release_program_continuity_command_center_acceptance_store
        self.unified_release_program_continuity_command_center_signoff_store = composition.unified_release_program_continuity_command_center_signoff_store
        self.unified_release_program_continuity_command_center_store = composition.unified_release_program_continuity_command_center_store
        self.unified_release_program_continuity_distribution_store = composition.unified_release_program_continuity_distribution_store
        self.unified_release_program_continuity_store = composition.unified_release_program_continuity_store
        self.unified_release_program_handoff_store = composition.unified_release_program_handoff_store
        self.unified_release_program_vault_operations_store = composition.unified_release_program_vault_operations_store
        self.unified_release_program_vault_store = composition.unified_release_program_vault_store

    def _execute_part_01(self, method: str, release_id: str, _split_state):
        if method == 'GET':
            _split_state['signoff'] = self.release_store.read_signoff(release_id, default={})
            self._send_json({'ok': True, 'release_id': release_id, 'signoff': _split_state['signoff'], 'summary': release_signoff_summary(_split_state['signoff'])})
            return (True, None)
        if method != 'POST':
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        _split_state['payload'] = self._optional_json_body()
        existing = self.release_store.read_signoff(release_id, default={})
        if existing:
            self._send_error(HTTPStatus.CONFLICT, 'Release is already signed off. Reset signoff before signing again.')
            return (True, None)
        _split_state['document'] = self.release_store.get_release(release_id)
        _split_state['report'] = self._get_or_refresh_release_qa(release_id, refresh=True, options={})
        _split_state['force'] = bool(_split_state['payload'].get('force', False))
        _split_state['acceptance_gate'] = self._release_acceptance_gate({**_split_state['payload'], 'release_id': release_id, 'force': _split_state['force']})
        policy_gate = self._release_declarative_policy_gate(_split_state['payload'])
        if policy_gate:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['evidence_policy'] = policy_gate
            if policy_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(policy_gate.get('message') or 'Release Evidence Graph policy failed.')
        audio_gate = self._release_audio_gate(release_id, _split_state['payload'])
        if audio_gate:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['audio'] = audio_gate
            if audio_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(audio_gate.get('message') or 'Release audio gate failed.')
        _split_state['require_mastering_qa'] = bool(_split_state['payload'].get('require_mastering_qa', False))
        _split_state['mastering_gate'] = self.mastering_store.gate(release_id, required=_split_state['require_mastering_qa'], profile_id=str(_split_state['payload'].get('mastering_profile_id') or '') or None, force=_split_state['force'])
        if _split_state['mastering_gate'] and _split_state['require_mastering_qa']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['mastering'] = _split_state['mastering_gate']
            if _split_state['mastering_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['mastering_gate'].get('message') or 'Mastering QA gate failed.')
        _split_state['require_encoded_audio'] = bool(_split_state['payload'].get('require_encoded_audio', False))
        required_encoded_profiles = normalize_required_profiles(_split_state['payload'].get('required_audio_format_profiles') or _split_state['payload'].get('audio_format_profiles') or [])
        _split_state['encoded_gate'] = encoded_audio_gate(self.audio_encoding_store, release_id, required_profiles=required_encoded_profiles, required=_split_state['require_encoded_audio'], force=_split_state['force'])
        if _split_state['encoded_gate'] and _split_state['require_encoded_audio']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['encoded_audio'] = _split_state['encoded_gate']
            if _split_state['encoded_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['encoded_gate'].get('message') or 'Encoded audio gate failed.')
        _split_state['require_encoded_audio_review'] = bool(_split_state['payload'].get('require_encoded_audio_review', False))
        _split_state['encoded_acceptance_gate'] = self.encoded_audio_acceptance_store.gate(release_id, required_profiles=required_encoded_profiles, required=_split_state['require_encoded_audio_review'], now=_utc_now())
        if _split_state['encoded_acceptance_gate'] and _split_state['require_encoded_audio_review']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['encoded_audio_acceptance'] = _split_state['encoded_acceptance_gate']
            if _split_state['encoded_acceptance_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['encoded_acceptance_gate'].get('message') or 'Encoded audio acceptance gate failed.')
        _split_state['require_format_decision'] = bool(_split_state['payload'].get('require_format_decision', False))
        _split_state['format_decision_gate'] = self.format_decision_store.gate(release_id, required=_split_state['require_format_decision'], session_id=str(_split_state['payload'].get('format_decision_session_id') or '') or None, required_profiles=required_encoded_profiles)
        if _split_state['format_decision_gate'] and _split_state['require_format_decision']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['format_decision'] = _split_state['format_decision_gate']
            if _split_state['format_decision_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['format_decision_gate'].get('message') or 'Format decision gate failed.')
        _split_state['require_rights_clearance'] = bool(_split_state['payload'].get('require_rights_clearance', False))
        _split_state['rights_gate'] = self.rights_clearance_store.gate(release_id, required=_split_state['require_rights_clearance'], now=_utc_now())
        return (False, None)

    def _execute_part_02(self, method: str, release_id: str, _split_state):
        if _split_state['rights_gate'] and _split_state['require_rights_clearance']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['rights_clearance'] = _split_state['rights_gate']
            if _split_state['rights_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['rights_gate'].get('message') or 'Rights clearance gate failed.')
        require_audio_campaign = bool(_split_state['payload'].get('require_audio_campaign', False))
        audio_campaign_gate = self._release_audio_campaign_gate(release_id, _split_state['payload'], required=require_audio_campaign)
        if audio_campaign_gate and require_audio_campaign:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['audio_campaign'] = audio_campaign_gate
            if audio_campaign_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(audio_campaign_gate.get('message') or 'Audio Campaign gate failed.')
        require_audio_campaign_remediation = bool(_split_state['payload'].get('require_audio_campaign_remediation', False))
        audio_campaign_remediation_gate = self.audio_campaign_remediation_store.gate(release_id, required=require_audio_campaign_remediation, require_signed=bool(_split_state['payload'].get('require_audio_campaign_remediation_signed', False)))
        if audio_campaign_remediation_gate and require_audio_campaign_remediation:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['audio_campaign_remediation'] = audio_campaign_remediation_gate
            if audio_campaign_remediation_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(audio_campaign_remediation_gate.get('message') or 'Audio Campaign remediation gate failed.')
        require_release_audio_certification = bool(_split_state['payload'].get('require_release_audio_certification', False))
        release_audio_certification_gate = self.release_audio_certification_store.gate(release_id, required=require_release_audio_certification, require_signed=bool(_split_state['payload'].get('require_release_audio_certification_signed', require_release_audio_certification)))
        if release_audio_certification_gate and require_release_audio_certification:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_certification'] = release_audio_certification_gate
            if release_audio_certification_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_certification_gate.get('message') or 'Release Audio Certification gate failed.')
        require_release_audio_timeline = bool(_split_state['payload'].get('require_release_audio_timeline', False))
        release_audio_timeline_gate = self.release_audio_timeline_store.gate(release_id, required=require_release_audio_timeline, require_signed=bool(_split_state['payload'].get('require_release_audio_timeline_signed', require_release_audio_timeline)), require_current_certification=bool(_split_state['payload'].get('require_release_audio_timeline_current_certification', True)))
        if release_audio_timeline_gate and require_release_audio_timeline:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_timeline'] = release_audio_timeline_gate
            if release_audio_timeline_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_timeline_gate.get('message') or 'Release Audio Timeline gate failed.')
        require_release_audio_regression = bool(_split_state['payload'].get('require_release_audio_regression_guard', False))
        release_audio_regression_gate = self.release_audio_regression_store.gate(release_id, required=require_release_audio_regression, require_signed=bool(_split_state['payload'].get('require_release_audio_regression_signed', require_release_audio_regression)))
        if release_audio_regression_gate and require_release_audio_regression:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_regression_guard'] = release_audio_regression_gate
            if release_audio_regression_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_regression_gate.get('message') or 'Release Audio Regression gate failed.')
        require_release_audio_baseline_governance = bool(_split_state['payload'].get('require_release_audio_baseline_governance', False))
        release_audio_baseline_governance_gate = self.release_audio_baseline_governance_store.gate(release_id, baseline_id=_split_state['payload'].get('release_audio_baseline_id'), required=require_release_audio_baseline_governance)
        if release_audio_baseline_governance_gate and require_release_audio_baseline_governance:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_baseline_governance'] = release_audio_baseline_governance_gate
            if release_audio_baseline_governance_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_baseline_governance_gate.get('message') or 'Release Audio Baseline Governance gate failed.')
        require_release_audio_regression_response = bool(_split_state['payload'].get('require_release_audio_regression_response', False))
        release_audio_regression_response_gate = self.release_audio_regression_response_store.gate(release_id, required=require_release_audio_regression_response, require_signed=bool(_split_state['payload'].get('require_release_audio_regression_response_signed', require_release_audio_regression_response)))
        if release_audio_regression_response_gate and require_release_audio_regression_response:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_regression_response'] = release_audio_regression_response_gate
            if release_audio_regression_response_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_regression_response_gate.get('message') or 'Release Audio Regression Response gate failed.')
        _split_state['require_release_audio_quality_observatory'] = bool(_split_state['payload'].get('require_release_audio_quality_observatory', False))
        _split_state['release_audio_quality_observatory_gate'] = self.release_audio_quality_observatory_store.gate(release_id, observatory_id=_split_state['payload'].get('release_audio_quality_observatory_id'), required=_split_state['require_release_audio_quality_observatory'], require_no_critical_risk=bool(_split_state['payload'].get('require_no_critical_audio_quality_risk', _split_state['require_release_audio_quality_observatory'])))
        return (False, None)

    def _execute_part_03(self, method: str, release_id: str, _split_state):
        if _split_state['release_audio_quality_observatory_gate'] and _split_state['require_release_audio_quality_observatory']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_quality_observatory'] = _split_state['release_audio_quality_observatory_gate']
            if _split_state['release_audio_quality_observatory_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['release_audio_quality_observatory_gate'].get('message') or 'Release Audio Quality Observatory gate failed.')
        require_release_audio_quality_action_queue = bool(_split_state['payload'].get('require_release_audio_quality_action_queue', False))
        release_audio_quality_action_queue_gate = self.release_audio_quality_action_queue_store.gate(release_id, queue_id=_split_state['payload'].get('release_audio_quality_action_queue_id'), required=require_release_audio_quality_action_queue, require_no_blocking=bool(_split_state['payload'].get('require_no_blocking_audio_quality_action', True)))
        if release_audio_quality_action_queue_gate and require_release_audio_quality_action_queue:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_quality_action_queue'] = release_audio_quality_action_queue_gate
            if release_audio_quality_action_queue_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_quality_action_queue_gate.get('message') or 'Release Audio Quality Action Queue gate failed.')
        require_release_audio_quality_action_queue_signoff = bool(_split_state['payload'].get('require_release_audio_quality_action_queue_signoff', False))
        release_audio_quality_action_queue_signoff_gate = self.release_audio_quality_action_signoff_store.gate(release_id, queue_id=_split_state['payload'].get('release_audio_quality_action_queue_id') or _split_state['payload'].get('release_audio_quality_action_queue_signoff_id'), required=require_release_audio_quality_action_queue_signoff)
        if release_audio_quality_action_queue_signoff_gate and require_release_audio_quality_action_queue_signoff:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_quality_action_queue_signoff'] = release_audio_quality_action_queue_signoff_gate
            if release_audio_quality_action_queue_signoff_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_quality_action_queue_signoff_gate.get('message') or 'Release Audio Quality Action Queue signoff gate failed.')
        require_release_audio_command_center = bool(_split_state['payload'].get('require_release_audio_command_center', False))
        release_audio_command_center_gate = self.release_audio_command_center_store.gate(release_id, required=require_release_audio_command_center, command_center_zip_path=_split_state['payload'].get('release_audio_command_center_zip') or _split_state['payload'].get('release_audio_command_center'), command_center_verification_report_path=_split_state['payload'].get('release_audio_command_center_verification_report'), evidence={'certification': {'zip': _split_state['payload'].get('release_audio_certification_zip'), 'verification_report': _split_state['payload'].get('release_audio_certification_verification_report')}, 'timeline': {'zip': _split_state['payload'].get('release_audio_timeline_zip'), 'verification_report': _split_state['payload'].get('release_audio_timeline_verification_report')}, 'regression': {'zip': _split_state['payload'].get('release_audio_regression_zip'), 'verification_report': _split_state['payload'].get('release_audio_regression_verification_report')}, 'baseline_governance': {'zip': _split_state['payload'].get('release_audio_baseline_registry_zip'), 'verification_report': _split_state['payload'].get('release_audio_baseline_registry_verification_report')}, 'regression_response': {'zip': _split_state['payload'].get('release_audio_regression_response_zip'), 'verification_report': _split_state['payload'].get('release_audio_regression_response_verification_report')}, 'observatory': {'zip': _split_state['payload'].get('release_audio_quality_observatory_zip'), 'verification_report': _split_state['payload'].get('release_audio_quality_observatory_verification_report')}, 'action_queue': {'zip': _split_state['payload'].get('release_audio_quality_action_queue_zip'), 'verification_report': _split_state['payload'].get('release_audio_quality_action_queue_verification_report')}, 'action_queue_signoff': {'zip': _split_state['payload'].get('release_audio_quality_action_queue_signoff_archive'), 'verification_report': _split_state['payload'].get('release_audio_quality_action_queue_signoff_verification_report')}, 'evidence_root': _split_state['payload'].get('release_audio_quality_observatory_evidence_root')})
        if release_audio_command_center_gate and require_release_audio_command_center:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['release_audio_command_center'] = release_audio_command_center_gate
            if release_audio_command_center_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(release_audio_command_center_gate.get('message') or 'Release Audio Command Center gate failed.')
        require_unified_command_center = bool(_split_state['payload'].get('require_unified_command_center', False))
        unified_command_center_gate = self.unified_command_center_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=require_unified_command_center, command_center_zip_path=_split_state['payload'].get('unified_command_center_zip') or _split_state['payload'].get('unified_command_center'), command_center_verification_report_path=_split_state['payload'].get('unified_command_center_verification_report'), evidence={'audio-command-center': {'zip': _split_state['payload'].get('release_audio_command_center_zip') or _split_state['payload'].get('release_audio_command_center'), 'verification_report': _split_state['payload'].get('release_audio_command_center_verification_report')}, 'ga-readiness': {'report': _split_state['payload'].get('ga_readiness_report')}, 'release-check': {'report': _split_state['payload'].get('release_check_report')}, 'requirements': {'require_audio_command_center': bool(_split_state['payload'].get('require_release_audio_command_center', False))}})
        if unified_command_center_gate and require_unified_command_center:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center'] = unified_command_center_gate
            if unified_command_center_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_gate.get('message') or 'Unified Command Center gate failed.')
        require_unified_command_center_archive = bool(_split_state['payload'].get('require_unified_command_center_archive', False))
        unified_command_center_archive_gate = self.unified_command_center_signoff_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=require_unified_command_center_archive, archive_zip_path=_split_state['payload'].get('unified_command_center_archive') or _split_state['payload'].get('unified_command_center_archive_zip'), archive_verification_report_path=_split_state['payload'].get('unified_command_center_archive_verification_report'))
        if unified_command_center_archive_gate and require_unified_command_center_archive:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_archive'] = unified_command_center_archive_gate
            if unified_command_center_archive_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_archive_gate.get('message') or 'Unified Command Center Archive gate failed.')
        _split_state['require_unified_command_center_handoff'] = bool(_split_state['payload'].get('require_unified_command_center_handoff', False))
        return (False, None)

    def _execute_part_04(self, method: str, release_id: str, _split_state):
        unified_command_center_handoff_gate = self.unified_command_center_handoff_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=_split_state['require_unified_command_center_handoff'], handoff_zip_path=_split_state['payload'].get('unified_command_center_handoff') or _split_state['payload'].get('unified_command_center_handoff_zip'), handoff_verification_report_path=_split_state['payload'].get('unified_command_center_handoff_verification_report'))
        if unified_command_center_handoff_gate and _split_state['require_unified_command_center_handoff']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_handoff'] = unified_command_center_handoff_gate
            if unified_command_center_handoff_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_handoff_gate.get('message') or 'Unified Command Center Handoff gate failed.')
        require_unified_command_center_continuous_review = bool(_split_state['payload'].get('require_unified_command_center_continuous_review', False))
        unified_command_center_continuous_review_gate = self.unified_command_center_continuous_review_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=require_unified_command_center_continuous_review, review_id=_split_state['payload'].get('unified_command_center_continuous_review_id'), review_zip_path=_split_state['payload'].get('unified_command_center_continuous_review') or _split_state['payload'].get('unified_command_center_continuous_review_zip'), review_verification_report_path=_split_state['payload'].get('unified_command_center_continuous_review_verification_report'), archive_zip_path=_split_state['payload'].get('unified_command_center_archive') or _split_state['payload'].get('unified_command_center_archive_zip'), archive_verification_report_path=_split_state['payload'].get('unified_command_center_archive_verification_report'), handoff_zip_path=_split_state['payload'].get('unified_command_center_handoff') or _split_state['payload'].get('unified_command_center_handoff_zip'), handoff_verification_report_path=_split_state['payload'].get('unified_command_center_handoff_verification_report'), command_center_zip_path=_split_state['payload'].get('unified_command_center_zip') or _split_state['payload'].get('unified_command_center'), command_center_verification_report_path=_split_state['payload'].get('unified_command_center_verification_report'), signoff_binding_path=_split_state['payload'].get('unified_command_center_signoff_binding'))
        if unified_command_center_continuous_review_gate and require_unified_command_center_continuous_review:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_continuous_review'] = unified_command_center_continuous_review_gate
            if unified_command_center_continuous_review_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_continuous_review_gate.get('message') or 'Unified Command Center Continuous Review gate failed.')
        require_unified_command_center_drift_response = bool(_split_state['payload'].get('require_unified_command_center_drift_response', False))
        unified_command_center_drift_response_gate = self.unified_command_center_drift_response_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=require_unified_command_center_drift_response, response_id=_split_state['payload'].get('unified_command_center_drift_response_id'), response_zip_path=_split_state['payload'].get('unified_command_center_drift_response') or _split_state['payload'].get('unified_command_center_drift_response_zip'), response_verification_report_path=_split_state['payload'].get('unified_command_center_drift_response_verification_report'), source_review_zip_path=_split_state['payload'].get('unified_command_center_drift_source_review') or _split_state['payload'].get('unified_command_center_drift_source_review_zip'), source_review_verification_report_path=_split_state['payload'].get('unified_command_center_drift_source_review_verification_report'), recheck_review_zip_path=_split_state['payload'].get('unified_command_center_drift_recheck_review') or _split_state['payload'].get('unified_command_center_drift_recheck_review_zip'), recheck_review_verification_report_path=_split_state['payload'].get('unified_command_center_drift_recheck_review_verification_report'), change_request_binding_report_path=_split_state['payload'].get('unified_command_center_drift_change_request_binding_report'), archive_zip_path=_split_state['payload'].get('unified_command_center_archive') or _split_state['payload'].get('unified_command_center_archive_zip'), archive_verification_report_path=_split_state['payload'].get('unified_command_center_archive_verification_report'), handoff_zip_path=_split_state['payload'].get('unified_command_center_handoff') or _split_state['payload'].get('unified_command_center_handoff_zip'), handoff_verification_report_path=_split_state['payload'].get('unified_command_center_handoff_verification_report'), command_center_zip_path=_split_state['payload'].get('unified_command_center_zip') or _split_state['payload'].get('unified_command_center'), command_center_verification_report_path=_split_state['payload'].get('unified_command_center_verification_report'), signoff_binding_path=_split_state['payload'].get('unified_command_center_signoff_binding'))
        if unified_command_center_drift_response_gate and require_unified_command_center_drift_response:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_drift_response'] = unified_command_center_drift_response_gate
            if unified_command_center_drift_response_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_drift_response_gate.get('message') or 'Unified Command Center Drift Response gate failed.')
        require_unified_command_center_evidence_review = bool(_split_state['payload'].get('require_unified_command_center_evidence_review', False))
        unified_command_center_evidence_review_gate = self.unified_command_center_evidence_review_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=require_unified_command_center_evidence_review, review_id=_split_state['payload'].get('unified_command_center_evidence_review_id'), review_zip_path=_split_state['payload'].get('unified_command_center_evidence_review') or _split_state['payload'].get('unified_command_center_evidence_review_zip'), review_verification_report_path=_split_state['payload'].get('unified_command_center_evidence_review_verification_report'), require_accepted=bool(_split_state['payload'].get('require_unified_command_center_evidence_review_accepted', False)), acceptance_zip_path=_split_state['payload'].get('unified_command_center_evidence_review_acceptance') or _split_state['payload'].get('unified_command_center_evidence_review_acceptance_zip'), acceptance_verification_report_path=_split_state['payload'].get('unified_command_center_evidence_review_acceptance_verification_report'), acceptance_response_verification_report_path=_split_state['payload'].get('unified_command_center_evidence_review_acceptance_response_verification_report'), payload=_split_state['payload'])
        if unified_command_center_evidence_review_gate and require_unified_command_center_evidence_review:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_evidence_review'] = unified_command_center_evidence_review_gate
            if unified_command_center_evidence_review_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_evidence_review_gate.get('message') or 'Unified Command Center Evidence Review gate failed.')
        _split_state['require_unified_command_center_reviewer_decision_board'] = bool(_split_state['payload'].get('require_unified_command_center_reviewer_decision_board', False))
        _split_state['unified_command_center_reviewer_decision_board_gate'] = self.unified_command_center_reviewer_decision_board_store.gate(str(_split_state['payload'].get('unified_command_center_id') or _split_state['payload'].get('unified_command_center_center_id') or 'ucc-000001'), required=_split_state['require_unified_command_center_reviewer_decision_board'], board_id=_split_state['payload'].get('unified_command_center_reviewer_decision_board_id'), archive_zip_path=_split_state['payload'].get('unified_command_center_reviewer_decision_board_archive') or _split_state['payload'].get('unified_command_center_reviewer_decision_board_zip'), verification_report_path=_split_state['payload'].get('unified_command_center_reviewer_decision_board_verification_report'), require_signed=bool(_split_state['payload'].get('require_unified_command_center_reviewer_decision_board_signed', True)), require_quorum=bool(_split_state['payload'].get('require_unified_command_center_reviewer_decision_board_quorum', True)), payload=_split_state['payload'])
        return (False, None)

    def _execute_part_05(self, method: str, release_id: str, _split_state):
        if _split_state['unified_command_center_reviewer_decision_board_gate'] and _split_state['require_unified_command_center_reviewer_decision_board']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_reviewer_decision_board'] = _split_state['unified_command_center_reviewer_decision_board_gate']
            if _split_state['unified_command_center_reviewer_decision_board_gate'].get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(_split_state['unified_command_center_reviewer_decision_board_gate'].get('message') or 'Unified Command Center Reviewer Decision Board gate failed.')
        require_unified_command_center_release_train = bool(_split_state['payload'].get('require_unified_command_center_release_train', False))
        unified_command_center_release_train_gate = self.unified_command_center_release_train_store.gate(str(_split_state['payload'].get('unified_command_center_release_train_id') or 'uct-000001'), required=require_unified_command_center_release_train, archive_zip_path=_split_state['payload'].get('unified_command_center_release_train_archive') or _split_state['payload'].get('unified_command_center_release_train_zip'), verification_report_path=_split_state['payload'].get('unified_command_center_release_train_verification_report'), external_evidence_manifest_path=_split_state['payload'].get('unified_command_center_release_train_external_evidence_manifest'), signoff_binding_path=_split_state['payload'].get('unified_command_center_release_train_signoff_binding'))
        if unified_command_center_release_train_gate and require_unified_command_center_release_train:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_command_center_release_train'] = unified_command_center_release_train_gate
            if unified_command_center_release_train_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_command_center_release_train_gate.get('message') or 'Unified Command Center Release Train gate failed.')
        require_unified_release_program_handoff = bool(_split_state['payload'].get('require_unified_release_program_handoff', False))
        unified_release_program_handoff_gate = self.unified_release_program_handoff_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_handoff_program_id') or 'urp-000001'), required=require_unified_release_program_handoff, handoff_archive_zip_path=_split_state['payload'].get('unified_release_program_handoff_archive') or _split_state['payload'].get('unified_release_program_handoff_zip'), handoff_archive_verification_report_path=_split_state['payload'].get('unified_release_program_handoff_verification_report'), external_evidence_manifest=_split_state['payload'].get('unified_release_program_handoff_external_evidence_manifest'), handoff_signoff_binding=_split_state['payload'].get('unified_release_program_handoff_signoff_binding'))
        if unified_release_program_handoff_gate and require_unified_release_program_handoff:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_handoff'] = unified_release_program_handoff_gate
            if unified_release_program_handoff_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_handoff_gate.get('message') or 'Unified Release Program Handoff gate failed.')
        require_unified_release_program_vault = bool(_split_state['payload'].get('require_unified_release_program_vault', False))
        unified_release_program_vault_gate = self.unified_release_program_vault_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_vault_program_id') or 'urp-000001'), required=require_unified_release_program_vault, vault_zip_path=_split_state['payload'].get('unified_release_program_vault') or _split_state['payload'].get('unified_release_program_vault_zip'), vault_verification_report_path=_split_state['payload'].get('unified_release_program_vault_verification_report'), vault_anchor_path=_split_state['payload'].get('unified_release_program_vault_anchor'), require_current_program=bool(_split_state['payload'].get('unified_release_program_vault_require_current_program', False)), require_current_operations=bool(_split_state['payload'].get('unified_release_program_vault_require_current_operations', False)), require_current_handoff=bool(_split_state['payload'].get('unified_release_program_vault_require_current_handoff', False)), require_accepted_evidence=bool(_split_state['payload'].get('unified_release_program_vault_require_accepted_evidence', True)))
        if unified_release_program_vault_gate and require_unified_release_program_vault:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_vault'] = unified_release_program_vault_gate
            if unified_release_program_vault_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_vault_gate.get('message') or 'Unified Release Program Evidence Vault gate failed.')
        require_unified_release_program_vault_operations = bool(_split_state['payload'].get('require_unified_release_program_vault_operations', False))
        unified_release_program_vault_operations_gate = self.unified_release_program_vault_operations_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_vault_operations_program_id') or 'urp-000001'), required=require_unified_release_program_vault_operations, archive_zip_path=_split_state['payload'].get('unified_release_program_vault_operations') or _split_state['payload'].get('unified_release_program_vault_operations_archive'), verification_report_path=_split_state['payload'].get('unified_release_program_vault_operations_verification_report'), signoff_binding_path=_split_state['payload'].get('unified_release_program_vault_operations_signoff_binding'))
        if unified_release_program_vault_operations_gate and require_unified_release_program_vault_operations:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_vault_operations'] = unified_release_program_vault_operations_gate
            if unified_release_program_vault_operations_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_vault_operations_gate.get('message') or 'Unified Release Program Vault Operations gate failed.')
        require_unified_release_program_continuity = bool(_split_state['payload'].get('require_unified_release_program_continuity', False))
        unified_release_program_continuity_gate = self.unified_release_program_continuity_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_program_id') or 'urp-000001'), required=require_unified_release_program_continuity, archive_zip_path=_split_state['payload'].get('unified_release_program_continuity') or _split_state['payload'].get('unified_release_program_continuity_archive'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_verification_report'), signoff_binding_path=_split_state['payload'].get('unified_release_program_continuity_signoff_binding'), vault_operations_archive_path=_split_state['payload'].get('unified_release_program_vault_operations') or _split_state['payload'].get('unified_release_program_vault_operations_archive'), vault_operations_verification_report_path=_split_state['payload'].get('unified_release_program_vault_operations_verification_report'), vault_operations_signoff_binding_path=_split_state['payload'].get('unified_release_program_vault_operations_signoff_binding'))
        if unified_release_program_continuity_gate and require_unified_release_program_continuity:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity'] = unified_release_program_continuity_gate
            if unified_release_program_continuity_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_gate.get('message') or 'Unified Release Program Continuity gate failed.')
        _split_state['require_unified_release_program_continuity_kit'] = bool(_split_state['payload'].get('require_unified_release_program_continuity_kit', False))
        return (False, None)

    def _execute_part_06(self, method: str, release_id: str, _split_state):
        unified_release_program_continuity_kit_gate = self.unified_release_program_continuity_distribution_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_kit_program_id') or 'urp-000001'), required=_split_state['require_unified_release_program_continuity_kit'], kit_zip_path=_split_state['payload'].get('unified_release_program_continuity_kit') or _split_state['payload'].get('unified_release_program_continuity_kit_zip'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_kit_verification_report'), receiver_receipt_path=_split_state['payload'].get('unified_release_program_continuity_kit_receiver_receipt'), require_receiver_receipt=bool(_split_state['payload'].get('require_unified_release_program_continuity_kit_receiver_receipt', False)))
        if unified_release_program_continuity_kit_gate and _split_state['require_unified_release_program_continuity_kit']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_kit'] = unified_release_program_continuity_kit_gate
            if unified_release_program_continuity_kit_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_kit_gate.get('message') or 'Unified Release Program Continuity Distribution Kit gate failed.')
        require_unified_release_program_continuity_acceptance = bool(_split_state['payload'].get('require_unified_release_program_continuity_acceptance', False))
        unified_release_program_continuity_acceptance_gate = self.unified_release_program_continuity_acceptance_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_acceptance_program_id') or 'urp-000001'), required=require_unified_release_program_continuity_acceptance, archive_zip_path=_split_state['payload'].get('unified_release_program_continuity_acceptance') or _split_state['payload'].get('unified_release_program_continuity_acceptance_archive'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_acceptance_verification_report'), continuity_kit=_split_state['payload'].get('unified_release_program_continuity_kit') or _split_state['payload'].get('unified_release_program_continuity_kit_zip'), continuity_kit_verification_report=_split_state['payload'].get('unified_release_program_continuity_kit_verification_report'), signoff_binding=_split_state['payload'].get('unified_release_program_continuity_acceptance_signoff_binding'))
        if unified_release_program_continuity_acceptance_gate and require_unified_release_program_continuity_acceptance:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_acceptance'] = unified_release_program_continuity_acceptance_gate
            if unified_release_program_continuity_acceptance_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_acceptance_gate.get('message') or 'Unified Release Program Continuity Acceptance gate failed.')
        require_unified_release_program_continuity_command_center = bool(_split_state['payload'].get('require_unified_release_program_continuity_command_center', False))
        unified_release_program_continuity_command_center_gate = self.unified_release_program_continuity_command_center_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_command_center_program_id') or 'urp-000001'), required=require_unified_release_program_continuity_command_center, command_center_zip_path=_split_state['payload'].get('unified_release_program_continuity_command_center') or _split_state['payload'].get('unified_release_program_continuity_command_center_zip'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_command_center_verification_report'), evidence_manifest_path=_split_state['payload'].get('unified_release_program_continuity_command_center_external_evidence_manifest'))
        if unified_release_program_continuity_command_center_gate and require_unified_release_program_continuity_command_center:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_command_center'] = unified_release_program_continuity_command_center_gate
            if unified_release_program_continuity_command_center_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_command_center_gate.get('message') or 'Unified Release Program Continuity Command Center gate failed.')
        require_unified_release_program_continuity_command_center_signoff = bool(_split_state['payload'].get('require_unified_release_program_continuity_command_center_signoff', False))
        unified_release_program_continuity_command_center_signoff_gate = self.unified_release_program_continuity_command_center_signoff_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_command_center_program_id') or 'urp-000001'), required=require_unified_release_program_continuity_command_center_signoff, archive_zip_path=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_archive'), archive_verification_report_path=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_verification_report'), signoff_binding_path=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_binding'), command_center_zip_path=_split_state['payload'].get('unified_release_program_continuity_command_center') or _split_state['payload'].get('unified_release_program_continuity_command_center_zip'), command_center_verification_report_path=_split_state['payload'].get('unified_release_program_continuity_command_center_verification_report'), command_center_external_evidence_manifest_path=_split_state['payload'].get('unified_release_program_continuity_command_center_external_evidence_manifest'))
        if unified_release_program_continuity_command_center_signoff_gate and require_unified_release_program_continuity_command_center_signoff:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_command_center_signoff'] = unified_release_program_continuity_command_center_signoff_gate
            if unified_release_program_continuity_command_center_signoff_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_command_center_signoff_gate.get('message') or 'Unified Release Program Continuity Command Center signoff gate failed.')
        require_unified_release_program_continuity_command_center_acceptance = bool(_split_state['payload'].get('require_unified_release_program_continuity_command_center_acceptance', False))
        unified_release_program_continuity_command_center_acceptance_gate = self.unified_release_program_continuity_command_center_acceptance_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_command_center_program_id') or 'urp-000001'), required=require_unified_release_program_continuity_command_center_acceptance, archive_zip_path=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_archive'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_verification_report'), acceptance_signoff_binding=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_signoff_binding'), review_pack=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_review_pack'), review_pack_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_review_pack_verification_report'), accepted_evidence_dir=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir'), response_proof_dir=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_response_proof_dir'), command_center_signoff_archive=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_archive'), command_center_signoff_archive_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_verification_report'), command_center_final_handoff=_split_state['payload'].get('unified_release_program_continuity_command_center_final_handoff'), command_center_final_handoff_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_final_handoff_verification_report'), command_center_signoff_binding=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_binding'), command_center=_split_state['payload'].get('unified_release_program_continuity_command_center'), command_center_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_verification_report'), command_center_evidence_manifest=_split_state['payload'].get('unified_release_program_continuity_command_center_external_evidence_manifest'))
        if unified_release_program_continuity_command_center_acceptance_gate and require_unified_release_program_continuity_command_center_acceptance:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_command_center_acceptance'] = unified_release_program_continuity_command_center_acceptance_gate
            if unified_release_program_continuity_command_center_acceptance_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(unified_release_program_continuity_command_center_acceptance_gate.get('message') or 'Unified Release Program Continuity Command Center Receiver Acceptance gate failed.')
        _split_state['require_receiver_acceptance_change'] = bool(_split_state['payload'].get('require_unified_release_program_continuity_command_center_acceptance_change_control', False))
        return (False, None)

    def _execute_part_07(self, method: str, release_id: str, _split_state):
        receiver_acceptance_change_gate = self.unified_release_program_continuity_command_center_acceptance_change_store.gate(str(_split_state['payload'].get('unified_release_program_id') or _split_state['payload'].get('unified_release_program_continuity_command_center_program_id') or 'urp-000001'), required=_split_state['require_receiver_acceptance_change'], archive_zip_path=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_change_archive'), verification_report_path=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_change_verification_report'), acceptance_archive=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_archive'), acceptance_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_verification_report'), acceptance_signoff_binding=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_signoff_binding'), previous_acceptance_root=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_previous_root'), review_pack=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_review_pack'), review_pack_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_review_pack_verification_report'), accepted_evidence_dir=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir'), response_proof_dir=_split_state['payload'].get('unified_release_program_continuity_command_center_acceptance_response_proof_dir'), command_center_signoff_archive=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_archive'), command_center_signoff_archive_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_verification_report'), command_center_final_handoff=_split_state['payload'].get('unified_release_program_continuity_command_center_final_handoff'), command_center_final_handoff_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_final_handoff_verification_report'), command_center_signoff_binding=_split_state['payload'].get('unified_release_program_continuity_command_center_signoff_binding'), command_center=_split_state['payload'].get('unified_release_program_continuity_command_center'), command_center_verification_report=_split_state['payload'].get('unified_release_program_continuity_command_center_verification_report'), command_center_evidence_manifest=_split_state['payload'].get('unified_release_program_continuity_command_center_external_evidence_manifest'))
        if receiver_acceptance_change_gate and _split_state['require_receiver_acceptance_change']:
            _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
            _split_state['acceptance_gate']['unified_release_program_continuity_command_center_acceptance_change_control'] = receiver_acceptance_change_gate
            if receiver_acceptance_change_gate.get('status') == 'failed':
                _split_state['acceptance_gate']['status'] = 'failed'
                _split_state['acceptance_gate']['message'] = str(receiver_acceptance_change_gate.get('message') or 'Receiver Acceptance Change Control gate failed.')
        policy_decision = evaluate_legacy_release_policy(_split_state['payload'], _split_state['acceptance_gate'], release_id=release_id, qa_passed=release_qa_allows_signoff(_split_state['report']) or _split_state['force'])
        _split_state['acceptance_gate']['policy_gate'] = policy_decision
        _split_state['acceptance_gate']['legacy_require_summary'] = policy_decision['legacy_require_summary']
        _split_state['acceptance_gate']['status'] = policy_decision['status']
        if policy_decision['status'] != 'passed':
            message = str(_split_state['acceptance_gate'].get('message') or 'Release Evidence Policy gate failed.')
            self._send_json({'error': message, 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
            return (True, None)
        if not release_qa_allows_signoff(_split_state['report']) and (not _split_state['force']):
            self._send_error(HTTPStatus.CONFLICT, 'Release QA gate failed. Refresh QA or pass force=true with override_reason.')
            return (True, None)
        if _split_state['force'] and (not str(_split_state['payload'].get('override_reason') or '').strip()):
            self._send_error(HTTPStatus.BAD_REQUEST, 'override_reason is required when force=true.')
            return (True, None)
        try:
            _split_state['export_manifest'] = read_release_export_manifest(self.release_store, release_id)
        except FileNotFoundError:
            _split_state['export_manifest'] = {}
        if _split_state['require_mastering_qa']:
            if not _split_state['export_manifest']:
                self._send_json({'error': 'Release Export has not been generated.', 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
            mastering_export_gate = self._release_mastering_export_gate(_split_state['export_manifest'], _split_state['mastering_gate'])
            if mastering_export_gate.get('status') == 'failed':
                _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
                _split_state['acceptance_gate']['mastering_export'] = mastering_export_gate
                self._send_json({'error': str(mastering_export_gate.get('message') or 'Release Export is stale. Rebuild export before signoff.'), 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
        return (False, None)

    def _execute_part_08(self, method: str, release_id: str, _split_state):
        if _split_state['require_encoded_audio']:
            if not _split_state['export_manifest']:
                self._send_json({'error': 'Release Export has not been generated.', 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
            encoded_export_gate = self._release_encoded_audio_export_gate(_split_state['export_manifest'], _split_state['encoded_gate'])
            if encoded_export_gate.get('status') == 'failed':
                _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
                _split_state['acceptance_gate']['encoded_audio_export'] = encoded_export_gate
                self._send_json({'error': str(encoded_export_gate.get('message') or 'Release Export is stale. Rebuild export before signoff.'), 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
        if _split_state['require_encoded_audio_review']:
            if not _split_state['export_manifest']:
                self._send_json({'error': 'Release Export has not been generated.', 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
        if _split_state['require_format_decision']:
            if not _split_state['export_manifest']:
                self._send_json({'error': 'Release Export has not been generated.', 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
            format_decision_export_gate = self._release_format_decision_export_gate(_split_state['export_manifest'], _split_state['format_decision_gate'])
            if format_decision_export_gate.get('status') == 'failed':
                _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
                _split_state['acceptance_gate']['format_decision_export'] = format_decision_export_gate
                self._send_json({'error': str(format_decision_export_gate.get('message') or 'Release Export is stale. Rebuild export before signoff.'), 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
            encoded_acceptance_export_gate = self._release_encoded_audio_acceptance_export_gate(_split_state['export_manifest'], _split_state['encoded_acceptance_gate'])
            if encoded_acceptance_export_gate.get('status') == 'failed':
                _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
                _split_state['acceptance_gate']['encoded_audio_acceptance_export'] = encoded_acceptance_export_gate
                self._send_json({'error': str(encoded_acceptance_export_gate.get('message') or 'Release Export is stale. Rebuild export before signoff.'), 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
        if _split_state['require_rights_clearance']:
            if not _split_state['export_manifest']:
                self._send_json({'error': 'Release Export has not been generated.', 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
            rights_export_gate = self._release_rights_clearance_export_gate(_split_state['export_manifest'], _split_state['rights_gate'])
            if rights_export_gate.get('status') == 'failed':
                _split_state['acceptance_gate'] = dict(_split_state['acceptance_gate'] or {})
                _split_state['acceptance_gate']['rights_clearance_export'] = rights_export_gate
                self._send_json({'error': str(rights_export_gate.get('message') or 'Release Export is stale. Rebuild export before signoff.'), 'acceptance_gate': _split_state['acceptance_gate']}, status=HTTPStatus.CONFLICT)
                return (True, None)
        return (False, None)

    def _execute_part_09(self, method: str, release_id: str, _split_state):
        if not _split_state['export_manifest'] and (not _split_state['force']):
            self._send_error(HTTPStatus.CONFLICT, 'Release Export has not been generated.')
            return (True, None)
        if _split_state['export_manifest'] and (not _split_state['force']):
            if _split_state['export_manifest'].get('source_hash') != _split_state['report'].get('source_hash'):
                self._send_error(HTTPStatus.CONFLICT, 'Release Export is stale. Rebuild export before signoff.')
                return (True, None)
            zip_summary = _as_document(_split_state['export_manifest'].get('zip'))
            zip_path = self.release_store.zip_path(release_id)
            if bool(_split_state['payload'].get('require_zip', True)) and (not (zip_path.exists() and zip_path.is_file() and (not zip_path.is_symlink()) and zip_summary.get('entry_count'))):
                self._send_error(HTTPStatus.CONFLICT, 'Release ZIP has not been generated.')
                return (True, None)
        try:
            pending_signoff = build_release_signoff_record(release=_split_state['document'], report=_split_state['report'], payload={**_split_state['payload'], 'force': _split_state['force']}, export_manifest={}, now=_utc_now())
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return (True, None)
        if _split_state['acceptance_gate']:
            pending_signoff['acceptance_gate'] = _split_state['acceptance_gate']
        self.release_store.write_signoff(release_id, {**pending_signoff, 'export_manifest_hash': None})
        try:
            final_manifest = refresh_release_export_signoff_summary(self.release_store, release_id)
            final_manifest.pop('zip', None)
            final_hash = stable_hash(final_manifest)
            _split_state['signoff'] = {**pending_signoff, 'export_manifest_hash': final_hash}
            _split_state['signoff'] = self.release_store.write_signoff(release_id, _split_state['signoff'])
            refresh_release_export_signoff_summary(self.release_store, release_id)
            build_release_export_zip(self.release_store, release_id, now=_utc_now(), allow_signed=True)
        except FileNotFoundError:
            _split_state['signoff'] = self.release_store.write_signoff(release_id, pending_signoff)
        _split_state['document'] = self.release_store.update_signoff_summary(release_id, release_signoff_summary(_split_state['signoff']))
        self.release_store.append_event(release_id, 'release_force_signed' if _split_state['force'] else 'release_signed', {'status': _split_state['report'].get('status'), 'forced': _split_state['force']})
        self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'signoff': _split_state['signoff'], 'summary': release_signoff_summary(_split_state['signoff'])})
        return (False, None)

    def execute(self, method: str, release_id: str) -> None:
        _split_state: dict[str, object] = {}
        _split_result = self._execute_part_01(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_02(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_03(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_04(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_05(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_06(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_07(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_08(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._execute_part_09(method, release_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
