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

FORMAT_DECISION_BLOCKED_KEYS = _make_deferred_global('FORMAT_DECISION_BLOCKED_KEYS')
FormatDecisionError = _make_deferred_global('FormatDecisionError')
FormatDecisionNotFoundError = _make_deferred_global('FormatDecisionNotFoundError')
_decision_relevant_target_options = _make_deferred_global('_decision_relevant_target_options')
distribution_target_format_decision_coverage = _make_deferred_global('distribution_target_format_decision_coverage')
format_decision_export_summary = _make_deferred_global('format_decision_export_summary')
format_decision_session_integrity_ok = _make_deferred_global('format_decision_session_integrity_ok')
format_decision_source_hash = _make_deferred_global('format_decision_source_hash')
format_distribution_decision_summary_hash = _make_deferred_global('format_distribution_decision_summary_hash')
format_matrix_integrity_ok = _make_deferred_global('format_matrix_integrity_ok')
format_recommendation_integrity_ok = _make_deferred_global('format_recommendation_integrity_ok')
format_report_integrity_ok = _make_deferred_global('format_report_integrity_ok')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
row = _make_deferred_global('row')
track = _make_deferred_global('track')

def bind_globals(namespace: dict[str, object]) -> None:
    global FORMAT_DECISION_BLOCKED_KEYS, FormatDecisionError, FormatDecisionNotFoundError, _decision_relevant_target_options, distribution_target_format_decision_coverage, format_decision_export_summary, format_decision_session_integrity_ok
    global format_decision_source_hash, format_distribution_decision_summary_hash, format_matrix_integrity_ok, format_recommendation_integrity_ok, format_report_integrity_ok, item, key, row
    global track
    FORMAT_DECISION_BLOCKED_KEYS = namespace.get('FORMAT_DECISION_BLOCKED_KEYS', FORMAT_DECISION_BLOCKED_KEYS)
    FormatDecisionError = namespace.get('FormatDecisionError', FormatDecisionError)
    FormatDecisionNotFoundError = namespace.get('FormatDecisionNotFoundError', FormatDecisionNotFoundError)
    _decision_relevant_target_options = namespace.get('_decision_relevant_target_options', _decision_relevant_target_options)
    distribution_target_format_decision_coverage = namespace.get('distribution_target_format_decision_coverage', distribution_target_format_decision_coverage)
    format_decision_export_summary = namespace.get('format_decision_export_summary', format_decision_export_summary)
    format_decision_session_integrity_ok = namespace.get('format_decision_session_integrity_ok', format_decision_session_integrity_ok)
    format_decision_source_hash = namespace.get('format_decision_source_hash', format_decision_source_hash)
    format_distribution_decision_summary_hash = namespace.get('format_distribution_decision_summary_hash', format_distribution_decision_summary_hash)
    format_matrix_integrity_ok = namespace.get('format_matrix_integrity_ok', format_matrix_integrity_ok)
    format_recommendation_integrity_ok = namespace.get('format_recommendation_integrity_ok', format_recommendation_integrity_ok)
    format_report_integrity_ok = namespace.get('format_report_integrity_ok', format_report_integrity_ok)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    track = namespace.get('track', track)
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




class FormatDecisionStoreEvidenceMixin:
    def gate(
        self,
        release_id: str,
        *,
        required: bool = False,
        session_id: str | None = None,
        required_profiles: list[str] | None = None,
        now: str | None = None,
    ) -> DomainDocument:
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

    def distribution_gate(self, release_id: str, target: DistributionTarget, *, required: bool = False, session_id: str | None = None) -> DomainDocument:
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

    def export_release(self, release_id: str, export_dir: Path, *, session_id: str | None = None) -> DomainDocument:
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

    def export_distribution(self, release_id: str, target: DistributionTarget, export_dir: Path, *, session_id: str | None = None) -> DomainDocument:
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

    def source_state(self, release_id: str, profiles: list[str] | None = None, *, now: str | None = None) -> DomainDocument:
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

    def report_source_hash(self, release_id: str, session: DomainDocument, matrix: DomainDocument, recommendation: DomainDocument) -> str:
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

    def with_current_session_state(self, session: DomainDocument) -> DomainDocument:
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

    def with_current_matrix_state(self, matrix: DomainDocument) -> DomainDocument:
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

    def with_current_recommendation_state(self, recommendation: DomainDocument) -> DomainDocument:
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

    def with_current_report_state(self, report: DomainDocument) -> DomainDocument:
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

    def _read_acceptance_summary(self, release_id: str, profiles: list[str], *, now: str | None = None) -> DomainDocument:
        from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore

        store = EncodedAudioAcceptanceStore(self.release_store, project_store=self.project_store, audio_encoding_store=self.encoding_store)
        return store.build_summary(release_id, required_profiles=profiles, now=now)

    def _review_by_id(self, release_id: str, review_id: str) -> DomainDocument:
        if not review_id:
            return {}
        path = self.release_store.release_dir(release_id) / "encoded-audio" / "acceptance" / "reviews" / f"{review_id}.json"
        if not path.exists():
            return {}
        value = read_json(path)
        return _as_document(value)

    def _target_context(self, release_id: str) -> DomainDocument:
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

    def _append_event(self, release_id: str, session_id: str, event_type: str, payload: DomainDocument, now: str | None = None) -> None:
        path = self.session_dir(release_id, session_id) / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now or now_iso(), "type": event_type, "payload": payload}, blocked_keys=FORMAT_DECISION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
