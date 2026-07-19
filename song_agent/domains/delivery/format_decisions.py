# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import threading as threading
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_encoding import AudioEncodingStore as AudioEncodingStore, encoded_audio_summary_hash as encoded_audio_summary_hash, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_manifest_uses_fake as encoded_manifest_uses_fake, normalize_required_profiles as normalize_required_profiles, resolve_target_audio_format_profiles as resolve_target_audio_format_profiles
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, DistributionTarget as DistributionTarget
from song_agent.domains.creation.encoded_audio_acceptance import encoded_audio_acceptance_summary_hash as encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_integrity_ok as encoded_audio_acceptance_summary_integrity_ok
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.delivery.v142_fd_readiness import FormatDecisionStoreReadinessMixin
from song_agent.domains.delivery import v142_fd_readiness as _v142_fd_readiness
from song_agent.domains.delivery.v142_fd_evidence import FormatDecisionStoreEvidenceMixin
from song_agent.domains.delivery import v142_fd_evidence as _v142_fd_evidence



FORMAT_DECISION_SCHEMA_VERSION = 1
FORMAT_MATRIX_SCHEMA_VERSION = 1
FORMAT_RECOMMENDATION_SCHEMA_VERSION = 1
FORMAT_REPORT_SCHEMA_VERSION = 1
FORMAT_DECISION_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
FORMAT_DECISION_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_MATRIX_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_RECOMMENDATION_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
SESSION_STATUSES = {"draft", "recommended", "selected", "signed", "archived", "stale"}
PROFILE_ROLES = {"selected", "archive", "fallback", "rejected"}
ARCHIVE_COMPATIBLE_DISTRIBUTION_PROFILES = {"internal_archive"}


class FormatDecisionError(ValueError):
    pass


class FormatDecisionNotFoundError(FormatDecisionError):
    pass


class FormatDecisionStateError(FormatDecisionError):
    pass


class FormatDecisionStore(FormatDecisionStoreReadinessMixin, FormatDecisionStoreEvidenceMixin):
    def __init__(
        self,
        release_store: ReleaseStore,
        project_store: ProjectStore | None = None,
        encoding_store: AudioEncodingStore | None = None,
        distribution_store: DistributionStore | None = None,
    ) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.encoding_store = encoding_store or AudioEncodingStore(release_store, project_store=self.project_store)
        self.distribution_store = distribution_store or DistributionStore(release_store)
        self.profile_store = self.encoding_store.profile_store
        self.lock = threading.RLock()











































def score_profile(row: DomainDocument, *, release_type: str = "") -> DomainDocument:
    score = 50
    reasons = []
    breakdown = []

    def add(rule: str, delta: int) -> None:
        nonlocal score
        score += delta
        breakdown.append({"rule": rule, "delta": delta})
        if delta > 0:
            reasons.append(rule)

    if row.get("health_status") == "passed":
        add("health_passed", 20)
    elif row.get("health_status") == "warning":
        add("health_warning", -10)
    if int(row.get("manual_review_count") or 0) >= int(row.get("file_count") or 0) and int(row.get("file_count") or 0) > 0:
        add("manual_reviews_accepted", 20)
    elif int(row.get("synthetic_review_count") or 0) > 0:
        add("synthetic_only", -40)
    else:
        add("manual_review_missing", -40)
    average_rating = row.get("average_rating")
    if isinstance(average_rating, (int, float)) and average_rating >= 4.5:
        add("high_average_rating", 10)
    if str(row.get("format") or "") in {"flac", "wav"}:
        add("lossless_archive_candidate", 8)
    if int(row.get("distribution_required_count") or 0) > 0:
        add("distribution_required", 15)
    if str(row.get("format") or "") in {"mp3", "aac"} and int(row.get("average_size_bytes") or 0) and int(row.get("average_size_bytes") or 0) < 15 * 1024 * 1024:
        add("delivery_size_efficient", 5)
    if int(row.get("needs_fix_count") or 0) or int(row.get("rejected_count") or 0):
        add("review_needs_fix_or_rejected", -30)
    if row.get("stale"):
        add("stale_evidence", -50)
    if row.get("fake_evidence"):
        add("fake_evidence", -100)
    return {"score": max(0, min(100, score)), "score_breakdown": breakdown, "score_reasons": reasons}


def recommend_role(row: DomainDocument) -> str:
    if row.get("blockers") or row.get("fake_evidence") or int(row.get("score") or 0) < 45:
        return "rejected"
    if int(row.get("distribution_required_count") or 0) > 0:
        return "selected"
    if str(row.get("format") or "") in {"flac", "wav"} and int(row.get("score") or 0) >= 70:
        return "archive"
    if int(row.get("score") or 0) >= 65:
        return "fallback"
    return "rejected"


def format_decision_source_hash(session: DomainDocument) -> str:
    payload = {
        "release_id": session.get("release_id"),
        "candidate_profiles": session.get("candidate_profiles", []),
        "source": session.get("source", {}),
        "selected_profiles": session.get("selected_profiles", []),
        "archive_profiles": session.get("archive_profiles", []),
        "fallback_profiles": session.get("fallback_profiles", []),
        "rejected_profiles": session.get("rejected_profiles", []),
        "manual_decision": session.get("manual_decision", {}),
    }
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_decision_session_hash(session: DomainDocument) -> str:
    payload = {key: value for key, value in session.items() if key not in FORMAT_DECISION_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_decision_session_integrity_ok(session: DomainDocument) -> bool:
    expected = str(session.get("integrity_hash") or "")
    return bool(expected) and expected == format_decision_session_hash(session)


def format_matrix_hash(matrix: DomainDocument) -> str:
    payload = {key: value for key, value in matrix.items() if key not in FORMAT_MATRIX_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_matrix_integrity_ok(matrix: DomainDocument) -> bool:
    expected = str(matrix.get("integrity_hash") or "")
    return bool(expected) and expected == format_matrix_hash(matrix)


def format_recommendation_hash(recommendation: DomainDocument) -> str:
    payload = {key: value for key, value in recommendation.items() if key not in FORMAT_RECOMMENDATION_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_recommendation_integrity_ok(recommendation: DomainDocument) -> bool:
    expected = str(recommendation.get("integrity_hash") or "")
    return bool(expected) and expected == format_recommendation_hash(recommendation)


def format_report_hash(report: DomainDocument) -> str:
    payload = {key: value for key, value in report.items() if key not in FORMAT_REPORT_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_report_integrity_ok(report: DomainDocument) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == format_report_hash(report)


def format_decision_export_summary(report: DomainDocument, matrix: DomainDocument | None = None, recommendation: DomainDocument | None = None) -> DomainDocument:
    matrix = _as_document(matrix)
    recommendation = _as_document(recommendation)
    decision = _as_document(report.get("decision"))
    return sanitize_metadata(
        {
            "status": report.get("status") or "missing",
            "session_id": report.get("session_id"),
            "report_path": "format-decision/decision-report.json",
            "report_hash": report.get("integrity_hash"),
            "matrix_path": "format-decision/matrix.json" if matrix else None,
            "matrix_hash": matrix.get("integrity_hash"),
            "recommendation_path": "format-decision/recommendation.json" if recommendation else None,
            "recommendation_hash": recommendation.get("integrity_hash"),
            "selected_profiles": decision.get("selected_profiles", []),
            "archive_profiles": decision.get("archive_profiles", []),
            "fallback_profiles": decision.get("fallback_profiles", []),
            "rejected_profiles": decision.get("rejected_profiles", []),
        },
        blocked_keys=FORMAT_DECISION_BLOCKED_KEYS,
    )


def format_distribution_decision_summary_hash(summary: DomainDocument) -> str:
    payload = {key: value for key, value in summary.items() if key != "integrity_hash"}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_distribution_decision_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == format_distribution_decision_summary_hash(summary)


def distribution_target_format_decision_coverage(target: DistributionTarget | DomainDocument, required_profiles: list[str], decision: DomainDocument) -> DomainDocument:
    target_profile_id = _target_profile_id(target)
    required = normalize_required_profiles(required_profiles)
    selected = set(normalize_required_profiles(decision.get("selected_profiles", []) if isinstance(decision.get("selected_profiles"), list) else []))
    archive = set(normalize_required_profiles(decision.get("archive_profiles", []) if isinstance(decision.get("archive_profiles"), list) else []))
    archive_allowed = target_profile_id in ARCHIVE_COMPATIBLE_DISTRIBUTION_PROFILES
    covered: list[str] = []
    missing: list[str] = []
    role_incompatible: list[str] = []
    for profile_id in required:
        if profile_id in selected:
            covered.append(profile_id)
        elif profile_id in archive:
            if archive_allowed:
                covered.append(profile_id)
            else:
                role_incompatible.append(profile_id)
        else:
            missing.append(profile_id)
    return {
        "target_profile_id": target_profile_id,
        "allowed_roles": ["selected", "archive"] if archive_allowed else ["selected"],
        "archive_allowed": archive_allowed,
        "covered_profiles": sorted(covered),
        "missing_profiles": sorted(missing),
        "role_incompatible_profiles": sorted(role_incompatible),
    }


def _validate_session_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("fds-") or not text[4:].isdigit():
        raise FormatDecisionError("Invalid format decision session_id.")
    return text


def _safe_text(value: Any, fallback: str, limit: int) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())[:limit]
    return text or fallback


def _decision_relevant_target_options(options: Any) -> ImplementationDocument:
    data = _as_document(options)
    return {
        key: data.get(key)
        for key in ("audio_format_profiles", "primary_audio_format", "require_encoded_audio", "require_encoded_audio_review", "require_format_decision")
        if key in data
    }


def _target_profile_id(target: DistributionTarget | ImplementationDocument) -> str:
    if isinstance(target, DistributionTarget):
        return str(target.profile_id or "")
    if isinstance(target, dict):
        return str(target.get("profile_id") or "")
    return ""


def format_decision_redaction_findings(payload: DomainDocument) -> list[DomainDocument]:
    findings = []
    text = json.dumps(payload, ensure_ascii=False)
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"kind": "sensitive_value", "message": f"Format decision contains sensitive value pattern: {replacement}."})
    return sanitize_metadata(findings, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

_v142_fd_readiness.bind_globals(globals())
_v142_fd_evidence.bind_globals(globals())
