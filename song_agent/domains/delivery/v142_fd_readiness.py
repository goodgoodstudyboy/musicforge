# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import threading as threading
from pathlib import Path as Path
from song_agent.domains.quality.audio_encoding import AudioEncodingStore as AudioEncodingStore, encoded_audio_summary_hash as encoded_audio_summary_hash, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_manifest_uses_fake as encoded_manifest_uses_fake, normalize_required_profiles as normalize_required_profiles, resolve_target_audio_format_profiles as resolve_target_audio_format_profiles
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, DistributionTarget as DistributionTarget
from song_agent.domains.creation.encoded_audio_acceptance import encoded_audio_acceptance_summary_hash as encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_integrity_ok as encoded_audio_acceptance_summary_integrity_ok
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

FormatDecisionError = _make_deferred_global('FormatDecisionError')
FormatDecisionNotFoundError = _make_deferred_global('FormatDecisionNotFoundError')
FormatDecisionStateError = _make_deferred_global('FormatDecisionStateError')
_safe_text = _make_deferred_global('_safe_text')
_validate_session_id = _make_deferred_global('_validate_session_id')
format_decision_session_hash = _make_deferred_global('format_decision_session_hash')
format_decision_source_hash = _make_deferred_global('format_decision_source_hash')
format_matrix_hash = _make_deferred_global('format_matrix_hash')
format_recommendation_hash = _make_deferred_global('format_recommendation_hash')
format_report_hash = _make_deferred_global('format_report_hash')
format_report_integrity_ok = _make_deferred_global('format_report_integrity_ok')
item = _make_deferred_global('item')
recommend_role = _make_deferred_global('recommend_role')
score_profile = _make_deferred_global('score_profile')

def bind_globals(namespace: dict[str, object]) -> None:
    global FormatDecisionError, FormatDecisionNotFoundError, FormatDecisionStateError, _safe_text, _validate_session_id, format_decision_session_hash, format_decision_source_hash
    global format_matrix_hash, format_recommendation_hash, format_report_hash, format_report_integrity_ok, item, recommend_role, score_profile
    FormatDecisionError = namespace.get('FormatDecisionError', FormatDecisionError)
    FormatDecisionNotFoundError = namespace.get('FormatDecisionNotFoundError', FormatDecisionNotFoundError)
    FormatDecisionStateError = namespace.get('FormatDecisionStateError', FormatDecisionStateError)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _validate_session_id = namespace.get('_validate_session_id', _validate_session_id)
    format_decision_session_hash = namespace.get('format_decision_session_hash', format_decision_session_hash)
    format_decision_source_hash = namespace.get('format_decision_source_hash', format_decision_source_hash)
    format_matrix_hash = namespace.get('format_matrix_hash', format_matrix_hash)
    format_recommendation_hash = namespace.get('format_recommendation_hash', format_recommendation_hash)
    format_report_hash = namespace.get('format_report_hash', format_report_hash)
    format_report_integrity_ok = namespace.get('format_report_integrity_ok', format_report_integrity_ok)
    item = namespace.get('item', item)
    recommend_role = namespace.get('recommend_role', recommend_role)
    score_profile = namespace.get('score_profile', score_profile)
    _bind_deferred_defaults(namespace)


FORMAT_DECISION_SCHEMA_VERSION = 1
FORMAT_MATRIX_SCHEMA_VERSION = 1
FORMAT_RECOMMENDATION_SCHEMA_VERSION = 1
FORMAT_REPORT_SCHEMA_VERSION = 1
FORMAT_DECISION_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_MATRIX_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_RECOMMENDATION_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
FORMAT_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
SESSION_STATUSES = {"draft", "recommended", "selected", "signed", "archived", "stale"}
PROFILE_ROLES = {"selected", "archive", "fallback", "rejected"}
ARCHIVE_COMPATIBLE_DISTRIBUTION_PROFILES = {"internal_archive"}




class FormatDecisionStoreReadinessMixin:
    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "format-decisions"

    def sessions_dir(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "sessions"

    def session_dir(self, release_id: str, session_id: str) -> Path:
        return self.sessions_dir(release_id) / _validate_session_id(session_id)

    def session_path(self, release_id: str, session_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "session.json"

    def matrix_path(self, release_id: str, session_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "matrix.json"

    def recommendation_path(self, release_id: str, session_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "recommendation.json"

    def report_path(self, release_id: str, session_id: str) -> Path:
        return self.session_dir(release_id, session_id) / "decision-report.json"

    def active_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "active-session.json"

    def create_session(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        with self.lock:
            session_id = self._reserve_session_id(release_id)
            profiles = normalize_required_profiles(payload.get("candidate_profiles") or payload.get("profiles") or [])
            if not profiles:
                profiles = self._available_profiles(release_id)
            source = self.source_state(release_id, profiles, now=now)
            session = {
                "schema_version": FORMAT_DECISION_SCHEMA_VERSION,
                "session_id": session_id,
                "release_id": release_id,
                "name": _safe_text(payload.get("name"), "Main delivery format decision", 120),
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "source": source,
                "candidate_profiles": profiles,
                "target_context": self._target_context(release_id),
                "selected_profiles": [],
                "fallback_profiles": [],
                "archive_profiles": [],
                "rejected_profiles": [],
                "manual_decision": {},
            }
            session["source_hash"] = format_decision_source_hash(session)
            session["integrity_hash"] = format_decision_session_hash(session)
            write_json(self.session_path(release_id, session_id), session)
            self._append_event(release_id, session_id, "format_decision_session_created", {"profiles": profiles}, now)
            return self.with_current_session_state(session)

    def list_sessions(self, release_id: str, *, include_archived: bool = False) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        rows: list[DomainDocument] = []
        if not self.sessions_dir(release_id).exists():
            return rows
        for path in sorted(self.sessions_dir(release_id).glob("fds-*/session.json")):
            try:
                session = self.with_current_session_state(read_json(path))
            except Exception:
                continue
            if session.get("status") == "archived" and not include_archived:
                continue
            rows.append(session)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    def read_session(self, release_id: str, session_id: str) -> DomainDocument:
        path = self.session_path(release_id, session_id)
        if not path.exists():
            raise FormatDecisionNotFoundError(f"Format decision session not found: {session_id}.")
        return self.with_current_session_state(read_json(path))

    def archive_session(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        session = self.read_session(release_id, session_id)
        if session.get("status") == "signed":
            raise FormatDecisionStateError("Signed format decision sessions cannot be archived.")
        session["status"] = "archived"
        session["updated_at"] = now
        session["integrity_hash"] = format_decision_session_hash(session)
        write_json(self.session_path(release_id, session_id), session)
        active = self.read_active_session(release_id, default={})
        if active.get("session_id") == session_id and self.active_path(release_id).exists():
            self.active_path(release_id).unlink()
        self._append_event(release_id, session_id, "format_decision_session_archived", {}, now)
        return self.with_current_session_state(session)

    def build_matrix(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        session = self.read_session(release_id, session_id)
        profiles = normalize_required_profiles(session.get("candidate_profiles") or [])
        source = self.source_state(release_id, profiles, now=now)
        encoded_summary = self.encoding_store.get_summary(release_id, current=True)
        acceptance_summary = self._read_acceptance_summary(release_id, profiles, now=now)
        profile_rows = []
        track_rows_by_id: dict[str, DomainDocument] = {}
        target_requirements = self._target_requirements(release_id)
        manifests = {str(row.get("profile_id") or ""): row for row in encoded_summary.get("profiles", []) if isinstance(row, dict)}
        acceptance_profiles = {str(row.get("profile_id") or ""): row for row in acceptance_summary.get("profiles", []) if isinstance(row, dict)}
        acceptance_tracks = {
            (str(row.get("profile_id") or ""), str(row.get("track_id") or "")): row
            for row in acceptance_summary.get("tracks", [])
            if isinstance(row, dict)
        }
        release = self.release_store.get_release(release_id)
        for profile_id in profiles:
            manifest = self.encoding_store.read_manifest(release_id, profile_id, default={})
            profile = self.profile_store.get_profile(profile_id)
            manifest_summary = manifests.get(profile_id, {})
            acceptance_profile = acceptance_profiles.get(profile_id, {})
            tracks = _as_list(manifest.get("tracks"))
            sizes = [int(row.get("size_bytes") or 0) for row in tracks if isinstance(row, dict)]
            ratings = []
            manual_count = 0
            synthetic_count = 0
            needs_fix_count = 0
            rejected_count = 0
            warning_count = 0
            blockers = []
            warnings: list[object] = []
            if manifest.get("stale"):
                blockers.append("manifest_stale")
            if not manifest or not manifest_summary:
                blockers.append("encoded_manifest_missing")
            if not manifest.get("integrity_hash") or not encoded_manifest_integrity_ok(manifest):
                blockers.append("encoded_manifest_integrity")
            if encoded_manifest_uses_fake(manifest):
                blockers.append("fake_evidence")
            if acceptance_profile.get("status") not in {"passed", "warning"}:
                blockers.append("acceptance_not_passed")
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                track_id = str(track.get("track_id") or "")
                review_row = acceptance_tracks.get((profile_id, track_id), {})
                manual_count += int(review_row.get("manual_accepted_count") or 0)
                synthetic_count += int(review_row.get("synthetic_accepted_count") or 0)
                needs_fix_count += int(review_row.get("needs_fix_count") or 0)
                rejected_count += int(review_row.get("rejected_count") or 0)
                if review_row.get("status") not in {"accepted"}:
                    warning_count += 1
                review = self._review_by_id(release_id, str(review_row.get("accepted_review_id") or ""))
                if review.get("rating") is not None:
                    ratings.append(float(review.get("rating") or 0))
                track_entry = track_rows_by_id.setdefault(track_id, {"track_id": track_id, "profiles": []})
                track_entry["profiles"].append(
                    {
                        "profile_id": profile_id,
                        "health_status": review_row.get("status") or "missing",
                        "review_status": review_row.get("status") or "missing",
                        "rating": review.get("rating"),
                        "size_bytes": int(track.get("size_bytes") or 0),
                        "encoded_track_hash": track.get("output_sha256"),
                    }
                )
            required_targets = target_requirements.get(profile_id, [])
            row = {
                "profile_id": profile_id,
                "format": profile.format,
                "extension": profile.extension,
                "encoded_status": manifest_summary.get("status") or manifest.get("status") or "missing",
                "health_status": acceptance_profile.get("status") or "missing",
                "acceptance_status": acceptance_profile.get("status") or "missing",
                "manual_review_count": manual_count,
                "synthetic_review_count": synthetic_count,
                "file_count": len(sizes),
                "total_size_bytes": sum(sizes),
                "average_size_bytes": int(sum(sizes) / len(sizes)) if sizes else 0,
                "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "needs_fix_count": needs_fix_count,
                "rejected_count": rejected_count,
                "warning_count": warning_count,
                "distribution_required_count": len(required_targets),
                "distribution_target_ids": required_targets,
                "fake_evidence": "fake_evidence" in blockers,
                "stale": bool(manifest.get("stale")),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
            }
            row.update(score_profile(row, release_type=release.release_type))
            profile_rows.append(row)
        matrix = {
            "schema_version": FORMAT_MATRIX_SCHEMA_VERSION,
            "session_id": session_id,
            "release_id": release_id,
            "generated_at": now,
            "profiles": sorted(profile_rows, key=lambda item: str(item.get("profile_id") or "")),
            "tracks": sorted(track_rows_by_id.values(), key=lambda item: str(item.get("track_id") or "")),
            "source_hash": stable_hash(source),
            "source": source,
        }
        matrix["integrity_hash"] = format_matrix_hash(matrix)
        write_json(self.matrix_path(release_id, session_id), matrix)
        self._append_event(release_id, session_id, "format_decision_matrix_refreshed", {"profile_count": len(profile_rows)}, now)
        return self.with_current_matrix_state(matrix)

    def read_matrix(self, release_id: str, session_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.matrix_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision matrix not found.")
        return self.with_current_matrix_state(read_json(path))

    def build_recommendation(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        matrix = self.build_matrix(release_id, session_id, now=now)
        recommendations = []
        selected_defaults: list[str] = []
        archive_defaults: list[str] = []
        fallback_defaults: list[str] = []
        rejected_defaults: list[str] = []
        for row in matrix.get("profiles", []) if isinstance(matrix.get("profiles"), list) else []:
            profile_id = str(row.get("profile_id") or "")
            role = recommend_role(row)
            if role == "selected":
                selected_defaults.append(profile_id)
            elif role == "archive":
                archive_defaults.append(profile_id)
            elif role == "fallback":
                fallback_defaults.append(profile_id)
            elif role == "rejected":
                rejected_defaults.append(profile_id)
            recommendations.append(
                {
                    "profile_id": profile_id,
                    "role": role,
                    "score": row.get("score"),
                    "confidence": "high" if int(row.get("score") or 0) >= 80 and not row.get("blockers") else "low" if row.get("blockers") else "medium",
                    "reasons": row.get("score_reasons", []),
                    "warnings": row.get("warnings", []),
                    "blockers": row.get("blockers", []),
                }
            )
        if not selected_defaults:
            best_delivery = next((row for row in sorted(matrix.get("profiles", []), key=lambda item: int(item.get("score") or 0), reverse=True) if not row.get("blockers")), None)
            if best_delivery:
                selected_defaults.append(str(best_delivery.get("profile_id") or ""))
        recommendation = {
            "schema_version": FORMAT_RECOMMENDATION_SCHEMA_VERSION,
            "session_id": session_id,
            "release_id": release_id,
            "generated_at": now,
            "recommendations": recommendations,
            "selected_defaults": sorted(set(selected_defaults)),
            "archive_defaults": sorted(set(archive_defaults)),
            "fallback_defaults": sorted(set(fallback_defaults)),
            "rejected_defaults": sorted(set(rejected_defaults)),
            "source_hash": matrix.get("integrity_hash"),
            "matrix_hash": matrix.get("integrity_hash"),
        }
        recommendation["integrity_hash"] = format_recommendation_hash(recommendation)
        write_json(self.recommendation_path(release_id, session_id), recommendation)
        session = self.read_session(release_id, session_id)
        if session.get("status") == "draft":
            session["status"] = "recommended"
            session["updated_at"] = now
            session["integrity_hash"] = format_decision_session_hash(session)
            write_json(self.session_path(release_id, session_id), session)
        self._append_event(release_id, session_id, "format_decision_recommendation_refreshed", {"recommendation_count": len(recommendations)}, now)
        return self.with_current_recommendation_state(recommendation)

    def read_recommendation(self, release_id: str, session_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.recommendation_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision recommendation not found.")
        return self.with_current_recommendation_state(read_json(path))

    def select_profiles(self, release_id: str, session_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        session = self.read_session(release_id, session_id)
        matrix = self.read_matrix(release_id, session_id)
        available = {str(row.get("profile_id") or "") for row in matrix.get("profiles", []) if isinstance(row, dict)}
        selected = normalize_required_profiles(payload.get("selected_profiles") or payload.get("selected") or [])
        archive = normalize_required_profiles(payload.get("archive_profiles") or payload.get("archive") or [])
        fallback = normalize_required_profiles(payload.get("fallback_profiles") or payload.get("fallback") or [])
        rejected = normalize_required_profiles(payload.get("rejected_profiles") or payload.get("rejected") or [])
        for profile_id in [*selected, *archive, *fallback, *rejected]:
            if profile_id not in available:
                raise FormatDecisionError(f"Format profile is not in this decision matrix: {profile_id}.")
        if not selected:
            raise FormatDecisionError("At least one selected profile is required.")
        session.update(
            {
                "status": "selected",
                "selected_profiles": selected,
                "archive_profiles": archive,
                "fallback_profiles": fallback,
                "rejected_profiles": rejected,
                "manual_decision": {
                    "decided_by": _safe_text(payload.get("decided_by"), "local-user", 120),
                    "decided_at": now,
                    "reason": _safe_text(payload.get("reason"), "", 1000),
                },
                "updated_at": now,
            }
        )
        session["source"] = self.source_state(release_id, normalize_required_profiles(session.get("candidate_profiles") or []), now=now)
        session["source_hash"] = format_decision_source_hash(session)
        session["integrity_hash"] = format_decision_session_hash(session)
        write_json(self.session_path(release_id, session_id), session)
        self._append_event(release_id, session_id, "format_decision_profiles_selected", {"selected": selected, "archive": archive, "fallback": fallback, "rejected": rejected}, now)
        return self.with_current_session_state(session)

    def build_report(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        session = self.read_session(release_id, session_id)
        if not session.get("selected_profiles"):
            raise FormatDecisionStateError("Select delivery profiles before creating a format decision report.")
        matrix = self.read_matrix(release_id, session_id)
        recommendation = self.read_recommendation(release_id, session_id, default={})
        required_distribution_profiles = self.required_distribution_profiles(release_id)
        coverage_profiles = sorted(set(session.get("selected_profiles", []) + session.get("archive_profiles", []) + session.get("fallback_profiles", [])))
        missing_required = sorted(set(required_distribution_profiles) - set(coverage_profiles))
        selected_rejected = sorted(set(session.get("selected_profiles", [])) & set(session.get("rejected_profiles", [])))
        archive_rejected = sorted(set(session.get("archive_profiles", [])) & set(session.get("rejected_profiles", [])))
        selected_rows = [row for row in matrix.get("profiles", []) if isinstance(row, dict) and row.get("profile_id") in set(session.get("selected_profiles", []))]
        blockers = list(missing_required)
        blockers.extend(f"{profile}:selected_and_rejected" for profile in selected_rejected)
        blockers.extend(f"{profile}:archive_and_rejected" for profile in archive_rejected)
        for row in selected_rows:
            for blocker in row.get("blockers", []) if isinstance(row.get("blockers"), list) else []:
                blockers.append(f"{row.get('profile_id')}:{blocker}")
            if row.get("acceptance_status") != "passed":
                blockers.append(f"{row.get('profile_id')}:acceptance_not_passed")
        warnings = [f"{row.get('profile_id')}:warning" for row in selected_rows if int(row.get("warning_count") or 0) > 0]
        status = "failed" if blockers else "warning" if warnings else "passed"
        report = {
            "schema_version": FORMAT_REPORT_SCHEMA_VERSION,
            "report_id": "fdr-000001",
            "session_id": session_id,
            "release_id": release_id,
            "status": status,
            "generated_at": now,
            "decision": {
                "selected_profiles": list(session.get("selected_profiles", [])),
                "archive_profiles": list(session.get("archive_profiles", [])),
                "fallback_profiles": list(session.get("fallback_profiles", [])),
                "rejected_profiles": list(session.get("rejected_profiles", [])),
                "decided_by": (session.get("manual_decision") or {}).get("decided_by") if isinstance(session.get("manual_decision"), dict) else None,
                "decided_at": (session.get("manual_decision") or {}).get("decided_at") if isinstance(session.get("manual_decision"), dict) else None,
                "reason": (session.get("manual_decision") or {}).get("reason") if isinstance(session.get("manual_decision"), dict) else None,
            },
            "coverage": {
                "required_distribution_profiles": required_distribution_profiles,
                "covered_required_profiles": sorted(set(required_distribution_profiles) & set(coverage_profiles)),
                "missing_required_profiles": missing_required,
                "manual_review_coverage": "passed" if not any("acceptance_not_passed" in item for item in blockers) else "failed",
            },
            "matrix_hash": matrix.get("integrity_hash"),
            "recommendation_hash": recommendation.get("integrity_hash"),
            "source_hash": self.report_source_hash(release_id, session, matrix, recommendation),
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
        }
        report["integrity_hash"] = format_report_hash(report)
        write_json(self.report_path(release_id, session_id), report)
        self._append_event(release_id, session_id, "format_decision_report_refreshed", {"status": status}, now)
        return self.with_current_report_state(report)

    def read_report(self, release_id: str, session_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.report_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision report not found.")
        return self.with_current_report_state(read_json(path))

    def activate_session(self, release_id: str, session_id: str, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        _session = self.read_session(release_id, session_id)
        report = self.read_report(release_id, session_id)
        if report.get("status") not in {"passed", "warning"} or report.get("stale") or not format_report_integrity_ok(report):
            raise FormatDecisionStateError("Format decision report must be current before activation.")
        payload = {"session_id": session_id, "activated_at": now, "report_hash": report.get("integrity_hash")}
        write_json(self.active_path(release_id), payload)
        self._append_event(release_id, session_id, "format_decision_session_activated", {"report_hash": report.get("integrity_hash")}, now)
        return payload

    def read_active_session(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.active_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("No active format decision session.")
        value = read_json(path)
        return _as_document(value)

    def active_report(self, release_id: str, session_id: str | None = None) -> DomainDocument:
        active = {"session_id": session_id} if session_id else self.read_active_session(release_id, default={})
        sid = str(active.get("session_id") or "")
        if not sid:
            raise FormatDecisionNotFoundError("No active format decision session.")
        return self.read_report(release_id, sid)
