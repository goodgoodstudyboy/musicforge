from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

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


class FormatDecisionStore:
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

    def create_session(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def list_sessions(self, release_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        rows: list[dict[str, Any]] = []
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

    def read_session(self, release_id: str, session_id: str) -> dict[str, Any]:
        path = self.session_path(release_id, session_id)
        if not path.exists():
            raise FormatDecisionNotFoundError(f"Format decision session not found: {session_id}.")
        return self.with_current_session_state(read_json(path))

    def archive_session(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def build_matrix(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        session = self.read_session(release_id, session_id)
        profiles = normalize_required_profiles(session.get("candidate_profiles") or [])
        source = self.source_state(release_id, profiles, now=now)
        encoded_summary = self.encoding_store.get_summary(release_id, current=True)
        acceptance_summary = self._read_acceptance_summary(release_id, profiles, now=now)
        profile_rows = []
        track_rows_by_id: dict[str, dict[str, Any]] = {}
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
            warnings: list[_InferenceType] = []
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

    def read_matrix(self, release_id: str, session_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.matrix_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision matrix not found.")
        return self.with_current_matrix_state(read_json(path))

    def build_recommendation(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def read_recommendation(self, release_id: str, session_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.recommendation_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision recommendation not found.")
        return self.with_current_recommendation_state(read_json(path))

    def select_profiles(self, release_id: str, session_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
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

    def build_report(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def read_report(self, release_id: str, session_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id, session_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("Format decision report not found.")
        return self.with_current_report_state(read_json(path))

    def activate_session(self, release_id: str, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        _session = self.read_session(release_id, session_id)
        report = self.read_report(release_id, session_id)
        if report.get("status") not in {"passed", "warning"} or report.get("stale") or not format_report_integrity_ok(report):
            raise FormatDecisionStateError("Format decision report must be current before activation.")
        payload = {"session_id": session_id, "activated_at": now, "report_hash": report.get("integrity_hash")}
        write_json(self.active_path(release_id), payload)
        self._append_event(release_id, session_id, "format_decision_session_activated", {"report_hash": report.get("integrity_hash")}, now)
        return payload

    def read_active_session(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.active_path(release_id)
        if not path.exists():
            if default is not None:
                return default
            raise FormatDecisionNotFoundError("No active format decision session.")
        value = read_json(path)
        return _as_document(value)

    def active_report(self, release_id: str, session_id: str | None = None) -> dict[str, Any]:
        active = {"session_id": session_id} if session_id else self.read_active_session(release_id, default={})
        sid = str(active.get("session_id") or "")
        if not sid:
            raise FormatDecisionNotFoundError("No active format decision session.")
        return self.read_report(release_id, sid)

    def gate(
        self,
        release_id: str,
        *,
        required: bool = False,
        session_id: str | None = None,
        required_profiles: list[str] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "require_format_decision": False, "hard_block": False}
        try:
            active = {"session_id": session_id} if session_id else self.read_active_session(release_id, default={})
            sid = str(active.get("session_id") or "")
            if not sid:
                raise FormatDecisionNotFoundError("No active format decision session.")
            report = self.read_report(release_id, sid)
        except FormatDecisionError as exc:
            return {"status": "failed", "require_format_decision": True, "hard_block": True, "message": str(exc), "session_id": session_id}
        required_set = set(normalize_required_profiles(required_profiles or []))
        decision = _as_document(report.get("decision"))
        selected = set(decision.get("selected_profiles", []) if isinstance(decision.get("selected_profiles"), list) else [])
        missing = sorted(required_set - selected)
        failures = []
        if report.get("status") == "failed":
            failures.append("report_failed")
        if report.get("stale"):
            failures.append("report_stale")
        if not format_report_integrity_ok(report):
            failures.append("report_integrity")
        if missing:
            failures.extend(f"{profile}:required_not_selected" for profile in missing)
        failed = bool(failures)
        return {
            "status": "failed" if failed else "passed",
            "require_format_decision": True,
            "hard_block": failed,
            "message": "Format decision gate failed." if failed else "Format decision gate passed.",
            "session_id": report.get("session_id"),
            "report_hash": report.get("integrity_hash"),
            "selected_profiles": decision.get("selected_profiles", []) if isinstance(decision.get("selected_profiles"), list) else [],
            "archive_profiles": decision.get("archive_profiles", []) if isinstance(decision.get("archive_profiles"), list) else [],
            "fallback_profiles": decision.get("fallback_profiles", []) if isinstance(decision.get("fallback_profiles"), list) else [],
            "rejected_profiles": decision.get("rejected_profiles", []) if isinstance(decision.get("rejected_profiles"), list) else [],
            "required_profiles": sorted(required_set),
            "missing_profiles": missing,
            "failures": sorted(set(failures)),
        }

    def distribution_gate(self, release_id: str, target: DistributionTarget, *, required: bool = False, session_id: str | None = None) -> dict[str, Any]:
        profiles = [profile for profile in resolve_target_audio_format_profiles(target, self.distribution_store.resolve_target_template(target)) if profile != "wav_master"]
        gate = self.gate(release_id, required=required, session_id=session_id, required_profiles=[])
        if not required:
            return gate
        report = {}
        if gate.get("session_id"):
            try:
                report = self.read_report(release_id, str(gate.get("session_id") or ""))
            except FormatDecisionError:
                report = {}
        rejected = set(report.get("decision", {}).get("rejected_profiles", []) if isinstance(report.get("decision"), dict) else [])
        rejected_required = sorted(set(profiles) & rejected)
        decision = _as_document(report.get("decision"))
        coverage = distribution_target_format_decision_coverage(target, profiles, decision)
        missing_required = list(coverage["missing_profiles"])
        role_incompatible = list(coverage["role_incompatible_profiles"])
        if rejected_required:
            gate = {**gate, "status": "failed", "hard_block": True, "message": "Format decision rejects a required distribution profile.", "rejected_required_profiles": rejected_required}
        if missing_required:
            gate = {**gate, "status": "failed", "hard_block": True, "message": "Format decision does not cover required distribution profiles.", "missing_profiles": missing_required}
        if role_incompatible:
            gate = {**gate, "status": "failed", "hard_block": True, "message": "Format decision role is not compatible with this distribution target.", "role_incompatible_profiles": role_incompatible}
        gate["required_profiles"] = profiles
        gate["target_profile_id"] = target.profile_id
        gate["allowed_format_decision_roles"] = coverage["allowed_roles"]
        gate["covered_profiles"] = coverage["covered_profiles"]
        gate["archive_allowed"] = coverage["archive_allowed"]
        return gate

    def export_release(self, release_id: str, export_dir: Path, *, session_id: str | None = None) -> dict[str, Any]:
        active = {"session_id": session_id} if session_id else self.read_active_session(release_id, default={})
        sid = str(active.get("session_id") or "")
        if not sid:
            return {"status": "missing", "summary_path": None}
        report = self.read_report(release_id, sid)
        matrix = self.read_matrix(release_id, sid, default={})
        recommendation = self.read_recommendation(release_id, sid, default={})
        root = export_dir / "format-decision"
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "decision-report.json", report)
        if matrix:
            write_json(root / "matrix.json", matrix)
        if recommendation:
            write_json(root / "recommendation.json", recommendation)
        return format_decision_export_summary(report, matrix, recommendation)

    def export_distribution(self, release_id: str, target: DistributionTarget, export_dir: Path, *, session_id: str | None = None) -> dict[str, Any]:
        active = {"session_id": session_id} if session_id else self.read_active_session(release_id, default={})
        sid = str(active.get("session_id") or "")
        if not sid:
            return {"status": "missing", "summary_path": None}
        report = self.read_report(release_id, sid)
        required_profiles = [profile for profile in resolve_target_audio_format_profiles(target, self.distribution_store.resolve_target_template(target)) if profile != "wav_master"]
        decision = _as_document(report.get("decision"))
        coverage = distribution_target_format_decision_coverage(target, required_profiles, decision)
        missing = list(coverage["missing_profiles"])
        incompatible = list(coverage["role_incompatible_profiles"])
        summary = {
            "schema_version": 1,
            "target_id": target.target_id,
            "target_profile_id": target.profile_id,
            "session_id": sid,
            "required_profiles": required_profiles,
            "covered_profiles": coverage["covered_profiles"],
            "missing_profiles": missing,
            "role_incompatible_profiles": incompatible,
            "allowed_roles": coverage["allowed_roles"],
            "archive_allowed": coverage["archive_allowed"],
            "selected_profiles": decision.get("selected_profiles", []),
            "archive_profiles": decision.get("archive_profiles", []),
            "rejected_profiles": decision.get("rejected_profiles", []),
            "report_hash": report.get("integrity_hash"),
            "status": "failed" if missing or incompatible else "passed",
        }
        summary["integrity_hash"] = format_distribution_decision_summary_hash(summary)
        root = export_dir / "format-decision"
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "target-decision-summary.json", sanitize_metadata(summary, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))
        return sanitize_metadata({**summary, "summary_path": "format-decision/target-decision-summary.json"}, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

    def source_state(self, release_id: str, profiles: list[str] | None = None, *, now: str | None = None) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        profiles = sorted(normalize_required_profiles(profiles or []) or self._available_profiles(release_id))
        encoded_summary = self.encoding_store.get_summary(release_id, current=True, now=now)
        acceptance_summary = self._read_acceptance_summary(release_id, profiles, now=now)
        targets = self._target_context(release_id)
        return sanitize_metadata(
            {
                "release": {
                    "release_id": release.release_id,
                    "tracks": [
                        {
                            "track_id": track.track_id,
                            "project_id": track.project_id,
                            "version_id": track.version_id,
                            "disc_number": track.disc_number,
                            "track_number": track.track_number,
                        }
                        for track in release.tracks
                    ],
                },
                "profiles": profiles,
                "encoded_summary_hash": encoded_audio_summary_hash(encoded_summary) if encoded_summary else None,
                "encoded_summary_integrity": encoded_audio_summary_integrity_ok(encoded_summary) if encoded_summary else False,
                "encoded_acceptance_summary_hash": encoded_audio_acceptance_summary_hash(acceptance_summary) if acceptance_summary else None,
                "encoded_acceptance_integrity": encoded_audio_acceptance_summary_integrity_ok(acceptance_summary) if acceptance_summary else False,
                "distribution_targets_hash": stable_hash(targets),
                "distribution_targets": targets,
            },
            blocked_keys=FORMAT_DECISION_BLOCKED_KEYS,
        )

    def report_source_hash(self, release_id: str, session: dict[str, Any], matrix: dict[str, Any], recommendation: dict[str, Any]) -> str:
        return stable_hash(
            sanitize_metadata(
                {
                    "current_source": self.source_state(release_id, normalize_required_profiles(session.get("candidate_profiles") or [])),
                    "session": {
                        "session_id": session.get("session_id"),
                        "selected_profiles": session.get("selected_profiles"),
                        "archive_profiles": session.get("archive_profiles"),
                        "fallback_profiles": session.get("fallback_profiles"),
                        "rejected_profiles": session.get("rejected_profiles"),
                        "manual_decision": session.get("manual_decision"),
                    },
                    "matrix_hash": matrix.get("integrity_hash"),
                    "recommendation_hash": recommendation.get("integrity_hash"),
                },
                blocked_keys=FORMAT_DECISION_BLOCKED_KEYS,
            )
        )

    def with_current_session_state(self, session: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(_as_document(session), blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        reasons = []
        try:
            current_source = self.source_state(str(clean.get("release_id") or ""), normalize_required_profiles(clean.get("candidate_profiles") or []), now=str(clean.get("created_at") or "") or None)
            current_hash = stable_hash(current_source)
        except Exception as exc:
            current_hash = ""
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "source_unavailable")
        stored_source = _as_document(clean.get("source"))
        if current_hash and stable_hash(stored_source) != current_hash:
            reasons.append("source_changed")
        if str(clean.get("source_hash") or "") != format_decision_source_hash(clean):
            reasons.append("source_hash")
        if not format_decision_session_integrity_ok(clean):
            reasons.append("session_integrity")
        clean["current_source_hash"] = current_hash or None
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

    def with_current_matrix_state(self, matrix: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(_as_document(matrix), blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        reasons = []
        try:
            current_hash = stable_hash(self.source_state(str(clean.get("release_id") or ""), normalize_required_profiles([row.get("profile_id") for row in clean.get("profiles", []) if isinstance(row, dict)]), now=str(clean.get("generated_at") or "") or None))
        except Exception as exc:
            current_hash = ""
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "source_unavailable")
        if current_hash and str(clean.get("source_hash") or "") != current_hash:
            stored_source = _as_document(clean.get("source"))
            if stable_hash(stored_source) == current_hash:
                clean["source_hash"] = current_hash
            else:
                reasons.append("source_changed")
        integrity_payload = {key: value for key, value in clean.items() if key != "source_hash"}
        integrity_payload["source_hash"] = str(matrix.get("source_hash") or "")
        if not format_matrix_integrity_ok(integrity_payload):
            reasons.append("matrix_integrity")
        clean["current_source_hash"] = current_hash or None
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

    def with_current_recommendation_state(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(_as_document(recommendation), blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        reasons = []
        matrix = self.read_matrix(str(clean.get("release_id") or ""), str(clean.get("session_id") or ""), default={})
        if matrix and str(clean.get("matrix_hash") or clean.get("source_hash") or "") not in {str(matrix.get("integrity_hash") or ""), str(matrix.get("source_hash") or "")}:
            reasons.append("matrix_changed")
        if not format_recommendation_integrity_ok(clean):
            reasons.append("recommendation_integrity")
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

    def with_current_report_state(self, report: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(_as_document(report), blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        reasons = []
        try:
            session = self.read_session(str(clean.get("release_id") or ""), str(clean.get("session_id") or ""))
            matrix = self.read_matrix(str(clean.get("release_id") or ""), str(clean.get("session_id") or ""), default={})
            recommendation = self.read_recommendation(str(clean.get("release_id") or ""), str(clean.get("session_id") or ""), default={})
            if session.get("stale"):
                reasons.append("session_stale")
            if matrix.get("stale"):
                reasons.append("matrix_stale")
            if recommendation and recommendation.get("stale"):
                reasons.append("recommendation_stale")
            current_hash = self.report_source_hash(str(clean.get("release_id") or ""), session, matrix, recommendation)
            if str(clean.get("source_hash") or "") != current_hash:
                reasons.append("source_changed")
        except Exception as exc:
            reasons.append(sanitize_sensitive_text(str(exc))[:120] or "source_unavailable")
        if not format_report_integrity_ok(clean):
            reasons.append("report_integrity")
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(clean["stale_reasons"])
        clean["current"] = not clean["stale"]
        return sanitize_metadata(clean, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)

    def required_distribution_profiles(self, release_id: str) -> list[str]:
        result: list[str] = []
        for target in self.distribution_store.list_targets(release_id):
            for profile_id in resolve_target_audio_format_profiles(target, self.distribution_store.resolve_target_template(target)):
                if profile_id != "wav_master" and profile_id not in result:
                    result.append(profile_id)
        return sorted(result)

    def _available_profiles(self, release_id: str) -> list[str]:
        profiles = [str(row.get("profile_id") or "") for row in self.encoding_store.list_manifests(release_id, current=False) if isinstance(row, dict)]
        return sorted(profile for profile in profiles if profile)

    def _read_acceptance_summary(self, release_id: str, profiles: list[str], *, now: str | None = None) -> ImplementationDocument:
        from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore

        store = EncodedAudioAcceptanceStore(self.release_store, project_store=self.project_store, audio_encoding_store=self.encoding_store)
        return store.build_summary(release_id, required_profiles=profiles, now=now)

    def _review_by_id(self, release_id: str, review_id: str) -> ImplementationDocument:
        if not review_id:
            return {}
        path = self.release_store.release_dir(release_id) / "encoded-audio" / "acceptance" / "reviews" / f"{review_id}.json"
        if not path.exists():
            return {}
        value = read_json(path)
        return _as_document(value)

    def _target_context(self, release_id: str) -> ImplementationDocument:
        targets = []
        for target in self.distribution_store.list_targets(release_id):
            template = self.distribution_store.resolve_target_template(target)
            targets.append(
                {
                    "target_id": target.target_id,
                    "profile_id": target.profile_id,
                    "audio_format_profiles": [profile for profile in resolve_target_audio_format_profiles(target, template) if profile != "wav_master"],
                    "template_pack_id": target.template_pack_id,
                    "template_hash": target.template_hash,
                    "options_hash": stable_hash(_decision_relevant_target_options(target.options)),
                }
            )
        return {"distribution_target_ids": [row["target_id"] for row in targets], "targets": sorted(targets, key=lambda item: item["target_id"])}

    def _target_requirements(self, release_id: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for target in self.distribution_store.list_targets(release_id):
            for profile in resolve_target_audio_format_profiles(target, self.distribution_store.resolve_target_template(target)):
                if profile == "wav_master":
                    continue
                result.setdefault(profile, []).append(target.target_id)
        return {key: sorted(value) for key, value in result.items()}

    def _ensure_release_mutable(self, release_id: str) -> None:
        release = self.release_store.get_release(release_id)
        if release.status == "signed":
            raise ReleaseStateError("Signed releases cannot change format decisions. Reset release signoff first.")

    def _reserve_session_id(self, release_id: str) -> str:
        self.sessions_dir(release_id).mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            session_id = f"fds-{index:06d}"
            if not self.session_path(release_id, session_id).exists():
                return session_id
            index += 1

    def _append_event(self, release_id: str, session_id: str, event_type: str, payload: ImplementationDocument, now: str | None = None) -> None:
        path = self.session_dir(release_id, session_id) / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now or now_iso(), "type": event_type, "payload": payload}, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def score_profile(row: dict[str, Any], *, release_type: str = "") -> dict[str, Any]:
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


def recommend_role(row: dict[str, Any]) -> str:
    if row.get("blockers") or row.get("fake_evidence") or int(row.get("score") or 0) < 45:
        return "rejected"
    if int(row.get("distribution_required_count") or 0) > 0:
        return "selected"
    if str(row.get("format") or "") in {"flac", "wav"} and int(row.get("score") or 0) >= 70:
        return "archive"
    if int(row.get("score") or 0) >= 65:
        return "fallback"
    return "rejected"


def format_decision_source_hash(session: dict[str, Any]) -> str:
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


def format_decision_session_hash(session: dict[str, Any]) -> str:
    payload = {key: value for key, value in session.items() if key not in FORMAT_DECISION_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_decision_session_integrity_ok(session: dict[str, Any]) -> bool:
    expected = str(session.get("integrity_hash") or "")
    return bool(expected) and expected == format_decision_session_hash(session)


def format_matrix_hash(matrix: dict[str, Any]) -> str:
    payload = {key: value for key, value in matrix.items() if key not in FORMAT_MATRIX_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_matrix_integrity_ok(matrix: dict[str, Any]) -> bool:
    expected = str(matrix.get("integrity_hash") or "")
    return bool(expected) and expected == format_matrix_hash(matrix)


def format_recommendation_hash(recommendation: dict[str, Any]) -> str:
    payload = {key: value for key, value in recommendation.items() if key not in FORMAT_RECOMMENDATION_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_recommendation_integrity_ok(recommendation: dict[str, Any]) -> bool:
    expected = str(recommendation.get("integrity_hash") or "")
    return bool(expected) and expected == format_recommendation_hash(recommendation)


def format_report_hash(report: dict[str, Any]) -> str:
    payload = {key: value for key, value in report.items() if key not in FORMAT_REPORT_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_report_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == format_report_hash(report)


def format_decision_export_summary(report: dict[str, Any], matrix: dict[str, Any] | None = None, recommendation: dict[str, Any] | None = None) -> dict[str, Any]:
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


def format_distribution_decision_summary_hash(summary: dict[str, Any]) -> str:
    payload = {key: value for key, value in summary.items() if key != "integrity_hash"}
    return stable_hash(sanitize_metadata(payload, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS))


def format_distribution_decision_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == format_distribution_decision_summary_hash(summary)


def distribution_target_format_decision_coverage(target: DistributionTarget | dict[str, Any], required_profiles: list[str], decision: dict[str, Any]) -> dict[str, Any]:
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


def format_decision_redaction_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    text = json.dumps(payload, ensure_ascii=False)
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"kind": "sensitive_value", "message": f"Format decision contains sensitive value pattern: {replacement}."})
    return sanitize_metadata(findings, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
