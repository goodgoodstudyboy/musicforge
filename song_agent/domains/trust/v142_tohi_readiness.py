# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, list_or as _list_or
import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, TrustOperationsHubStore as TrustOperationsHubStore, hub_hash as hub_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import INCIDENT_EXPORT_ENTRIES as INCIDENT_EXPORT_ENTRIES, TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION as TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash

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

TrustOperationsIncidentNotFoundError = _make_deferred_global('TrustOperationsIncidentNotFoundError')
TrustOperationsIncidentStateError = _make_deferred_global('TrustOperationsIncidentStateError')
_board_summary = _make_deferred_global('_board_summary')
_contains_sensitive_value = _make_deferred_global('_contains_sensitive_value')
_default_plan_steps = _make_deferred_global('_default_plan_steps')
_next_id = _make_deferred_global('_next_id')
_now = _make_deferred_global('_now')
_read_json = _make_deferred_global('_read_json')
_read_json_default = _make_deferred_global('_read_json_default')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_valid_passed_evidence_for_incident = _make_deferred_global('_valid_passed_evidence_for_incident')
_write_json = _make_deferred_global('_write_json')
item = _make_deferred_global('item')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsIncidentNotFoundError, TrustOperationsIncidentStateError, _board_summary, _contains_sensitive_value, _default_plan_steps, _next_id, _now
    global _read_json, _read_json_default, _safe_id, _sanitize, _valid_passed_evidence_for_incident, _write_json, item, key
    TrustOperationsIncidentNotFoundError = namespace.get('TrustOperationsIncidentNotFoundError', TrustOperationsIncidentNotFoundError)
    TrustOperationsIncidentStateError = namespace.get('TrustOperationsIncidentStateError', TrustOperationsIncidentStateError)
    _board_summary = namespace.get('_board_summary', _board_summary)
    _contains_sensitive_value = namespace.get('_contains_sensitive_value', _contains_sensitive_value)
    _default_plan_steps = namespace.get('_default_plan_steps', _default_plan_steps)
    _next_id = namespace.get('_next_id', _next_id)
    _now = namespace.get('_now', _now)
    _read_json = namespace.get('_read_json', _read_json)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _valid_passed_evidence_for_incident = namespace.get('_valid_passed_evidence_for_incident', _valid_passed_evidence_for_incident)
    _write_json = namespace.get('_write_json', _write_json)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_report"
EVIDENCE_PACKAGE_TYPES = {
    "release_verification": "musicforge_release_verification",
    "distribution_verification": "musicforge_distribution_verification",
    "submission_verification": "musicforge_submission_verification",
    "submission_evidence_verification": "musicforge_submission_evidence_verification",
    "release_operations_verification": "musicforge_release_operations_verification",
    "publication_monitoring_verification": "musicforge_public_trust_center_publication_monitoring_verification",
}
BLOCKING_STATUSES = {"open", "triaged", "in_progress", "waiting_verification", "verified"}
SAFE_REMEDIATION_ACTIONS = {
    "refresh_hub_report",
    "export_hub",
    "zip_hub",
    "verify_hub",
    "create_hub_runbook",
    "run_hub_safe_actions",
    "verify_release_package",
    "verify_distribution_package",
    "verify_submission_package",
    "verify_submission_evidence_package",
    "verify_release_operations_package",
    "manual_required",
}
FORBIDDEN_REMEDIATION_ACTIONS = {
    "signoff",
    "reset_signoff",
    "approve_change_request",
    "submit",
    "mark_accepted",
    "provider_call",
    "upload_file",
    "manual_review",
    "delete_artifact",
    "force_close",
}




class TrustOperationsIncidentStoreReadinessMixin:
    def hub_dir(self, hub_id: str) -> Path:
        return self.root / _safe_id(hub_id)

    def board_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-board.json"

    def board_events_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-board-events.jsonl"

    def source_snapshot_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-source-snapshot.json"

    def incidents_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incidents"

    def incident_dir(self, hub_id: str, incident_id: str) -> Path:
        return self.incidents_dir(hub_id) / _safe_id(incident_id)

    def incident_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "incident.json"

    def incident_events_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "incident-events.jsonl"

    def plan_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "remediation-plan.json"

    def result_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "remediation-result.json"

    def evidence_dir(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "evidence"

    def evidence_index_path(self, hub_id: str, incident_id: str) -> Path:
        return self.evidence_dir(hub_id, incident_id) / "evidence-index.json"

    def evidence_path(self, hub_id: str, incident_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(hub_id, incident_id) / (_safe_id(evidence_id) + ".json")

    def closeout_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "closeout-report.json"

    def export_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "exports" / "current"

    def zip_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-board.zip"

    def verification_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-verification-report.json"

    def refresh_board(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            report_id = str(payload.get("report_id") or self._current_report_id(hub_id) or "")
            if not report_id:
                raise TrustOperationsIncidentStateError("Trust Operations Hub report is required.")
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
            self.hub_store._assert_external_sources_current(docs, self.hub_store._read_source_paths(hub_id, report_id))
            source = self._source_summary(hub_id, report_id, docs)
            existing_board = _read_json_default(self.board_path(hub_id), default={})
            existing = {
                str(item.get("detected_from", {}).get("source_fingerprint") or ""): item
                for item in self.list_incidents(hub_id, include_archived=True)
            }
            current_fingerprints: set[str] = set()
            created_count = 0
            updated_count = 0
            stale_count = 0
            incident_ids: list[str] = []
            for candidate in self._incident_candidates(hub_id, report_id, source, docs, now):
                fingerprint = str(candidate["detected_from"]["source_fingerprint"])
                current_fingerprints.add(fingerprint)
                if fingerprint in existing and existing[fingerprint].get("status") != "closed":
                    incident = existing[fingerprint]
                    incident.update(
                        {
                            "title": candidate["title"],
                            "description": candidate["description"],
                            "severity": candidate["severity"],
                            "blocking": candidate["blocking"],
                            "last_seen_at": now,
                            "source_resolved": False,
                            "stale": False,
                            "updated_at": now,
                            "detected_from": candidate["detected_from"],
                        }
                    )
                    updated_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_refreshed", now=now)
                else:
                    incident_id = _next_id(self.incidents_dir(hub_id), "inc")
                    incident = {
                        "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                        "hub_id": hub_id,
                        "incident_id": incident_id,
                        "title": candidate["title"],
                        "description": candidate["description"],
                        "category": candidate["category"],
                        "severity": candidate["severity"],
                        "blocking": candidate["blocking"],
                        "status": "open",
                        "created_at": now,
                        "updated_at": now,
                        "last_seen_at": now,
                        "source_resolved": False,
                        "detected_from": candidate["detected_from"],
                        "triage": {"status": "untriaged", "owner": None, "notes": "", "triaged_at": None},
                        "remediation_plan_id": None,
                        "closeout_report_id": None,
                        "stale": False,
                    }
                    created_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_created", now=now)
                incident_ids.append(str(incident["incident_id"]))
            for incident in self.list_incidents(hub_id, include_archived=True):
                if incident.get("status") in {"closed", "archived"}:
                    incident_ids.append(str(incident.get("incident_id") or ""))
                    continue
                fingerprint = str(incident.get("detected_from", {}).get("source_fingerprint") or "")
                if fingerprint and fingerprint not in current_fingerprints:
                    incident["source_resolved"] = True
                    incident["stale"] = False
                    incident["updated_at"] = now
                    updated_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_source_resolved", now=now)
                elif str(incident.get("detected_from", {}).get("hub_report_hash") or "") != str(source.get("hub_report_hash") or ""):
                    incident["stale"] = True
                    incident["updated_at"] = now
                    stale_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_marked_stale", now=now)
                incident_ids.append(str(incident.get("incident_id") or ""))
            board_id = str(existing_board.get("board_id") or "tohi-board-000001")
            board: DomainDocument = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE,
                "hub_id": hub_id,
                "board_id": board_id,
                "status": "open",
                "created_at": existing_board.get("created_at") or now,
                "updated_at": now,
                "source": source,
                "incident_ids": sorted(set(item for item in incident_ids if item)),
            }
            board["summary"] = _board_summary(self.list_incidents(hub_id, include_archived=False))
            board_summary = _as_document(board.get("summary"))
            if board_summary.get("open_count") == 0 and board_summary.get("stale_count") == 0:
                board["status"] = "ready_for_closeout"
            board["integrity_hash"] = incident_hash(board)
            _write_json(self.board_path(hub_id), board)
            _write_json(self.source_snapshot_path(hub_id), source)
            self._append_board_event(hub_id, "incident_board_refreshed", {"board_hash": board["integrity_hash"], "created_count": created_count, "updated_count": updated_count}, now=now)
            return _sanitize({"incident_board": board, "created_count": created_count, "updated_count": updated_count, "stale_count": stale_count, "incidents": self.list_incidents(hub_id)})

    def read_board(self, hub_id: str) -> DomainDocument:
        if not self.board_path(hub_id).exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident Board not found.")
        return _read_json(self.board_path(hub_id))

    def list_incidents(self, hub_id: str, *, include_archived: bool = False) -> list[DomainDocument]:
        root = self.incidents_dir(hub_id)
        if not root.exists():
            return []
        rows = []
        for path in sorted(root.glob("*/incident.json")):
            incident = _read_json(path)
            if incident.get("status") == "archived" and not include_archived:
                continue
            rows.append(_sanitize(incident))
        return rows

    def read_incident(self, hub_id: str, incident_id: str) -> DomainDocument:
        path = self.incident_path(hub_id, incident_id)
        if not path.exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident not found.")
        return _read_json(path)

    def triage_incident(self, hub_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            severity = str(payload.get("severity") or incident.get("severity") or "medium")
            if severity not in {"critical", "high", "medium", "low", "info"}:
                raise TrustOperationsIncidentStateError("Invalid incident severity.")
            incident["severity"] = severity
            incident["blocking"] = bool(payload.get("blocking", incident.get("blocking", False)))
            incident["status"] = "triaged" if incident.get("status") == "open" else incident.get("status")
            incident["triage"] = {
                "status": "triaged",
                "owner": sanitize_sensitive_text(str(payload.get("owner") or "local-user")[:120]),
                "notes": sanitize_sensitive_text(str(payload.get("notes") or "")[:1000]),
                "triaged_at": now,
            }
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_triaged", now=now)
            return _sanitize(incident)

    def create_plan(self, hub_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            plan_id = _safe_id(str(payload.get("plan_id") or "rp-000001"))
            steps = _list_or(payload.get("steps"), _default_plan_steps(incident))
            normalized = []
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                action_type = str(step.get("action_type") or "manual_required")
                if action_type in FORBIDDEN_REMEDIATION_ACTIONS or action_type not in SAFE_REMEDIATION_ACTIONS:
                    raise TrustOperationsIncidentStateError("Unsafe remediation action is not allowed.")
                normalized.append(
                    {
                        "step_id": str(step.get("step_id") or f"step-{index:03d}"),
                        "action_type": action_type,
                        "title": sanitize_sensitive_text(str(step.get("title") or action_type)[:200]),
                        "component_type": step.get("component_type") or incident.get("detected_from", {}).get("component_type"),
                        "component_id": step.get("component_id") or incident.get("detected_from", {}).get("component_id"),
                        "safe_auto": action_type != "manual_required",
                        "status": "pending",
                    }
                )
            plan = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "hub_id": hub_id,
                "incident_id": incident_id,
                "plan_id": plan_id,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "source_hash": incident.get("integrity_hash"),
                "steps": normalized,
            }
            plan["integrity_hash"] = incident_hash(plan)
            _write_json(self.plan_path(hub_id, incident_id), plan)
            incident["remediation_plan_id"] = plan_id
            if incident.get("status") in {"open", "triaged"}:
                incident["status"] = "in_progress"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_plan_created", now=now)
            return _sanitize(plan)

    def add_evidence(self, hub_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if any(key in payload for key in ("source_path", "local_path", "file_path")):
                raise TrustOperationsIncidentStateError("Evidence import does not accept source_path/local_path/file_path.")
            incident = self._mutable_incident(hub_id, incident_id)
            report = payload.get("report") if isinstance(payload.get("report"), dict) else None
            if report is None and payload.get("content_base64"):
                try:
                    raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
                    report = json.loads(raw.decode("utf-8"))
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise TrustOperationsIncidentStateError(f"Evidence content is not valid JSON: {exc}") from exc
            if report is None and isinstance(payload.get("content"), dict):
                report = payload["content"]
            if report is None:
                raise TrustOperationsIncidentStateError("Evidence JSON content is required.")
            if _contains_sensitive_value(report):
                raise TrustOperationsIncidentStateError("Evidence contains sensitive or local-path content.")
            component_type = str(payload.get("component_type") or incident.get("detected_from", {}).get("component_type") or "")
            component_id = str(payload.get("component_id") or incident.get("detected_from", {}).get("component_id") or "")
            binding = self._bind_evidence_to_hub(hub_id, incident, report, component_type, component_id)
            if binding.get("binding_status") != "passed":
                raise TrustOperationsIncidentStateError("Evidence does not match current Trust Operations Hub verification evidence.")
            evidence_id = _safe_id(str(payload.get("evidence_id") or _next_id(self.evidence_dir(hub_id, incident_id), "ev")))
            evidence = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "evidence_id": evidence_id,
                "incident_id": incident_id,
                "kind": str(payload.get("kind") or "external_verification_report"),
                "component_type": binding.get("component_type") or component_type,
                "component_id": binding.get("component_id") or component_id,
                "requested_component_id": component_id,
                "incident_component_id": incident.get("detected_from", {}).get("component_id"),
                "status": report.get("status") or "missing",
                "package_type": report.get("package_type"),
                "payload_hash": stable_hash(report),
                "verification_report_hash": verification_hash(report),
                "zip_sha256": report.get("zip_sha256"),
                "zip_size_bytes": report.get("zip_size_bytes"),
                "manifest_hash": report.get("manifest_hash"),
                "source_hash": report.get("source_hash"),
                "binding_status": binding.get("binding_status"),
                "binding_checks": binding.get("binding_checks") or [],
                "expected_evidence_id": binding.get("expected_evidence_id"),
                "expected_component_id": binding.get("expected_component_id"),
                "expected_component_type": binding.get("expected_component_type"),
                "expected_package_type": binding.get("expected_package_type"),
                "expected_verification_report_hash": binding.get("expected_verification_report_hash"),
                "expected_zip_sha256": binding.get("expected_zip_sha256"),
                "expected_zip_size_bytes": binding.get("expected_zip_size_bytes"),
                "expected_manifest_hash": binding.get("expected_manifest_hash"),
                "expected_source_hash": binding.get("expected_source_hash"),
                "expected_status": binding.get("expected_status"),
                "created_at": now,
                "redaction_status": "passed",
                "summary": _as_document(report.get("summary")),
            }
            evidence["integrity_hash"] = incident_hash(evidence)
            _write_json(self.evidence_path(hub_id, incident_id, evidence_id), evidence)
            self._write_evidence_index(hub_id, incident_id)
            if incident.get("status") in {"open", "triaged", "in_progress"}:
                incident["status"] = "waiting_verification"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_evidence_added", now=now)
            return _sanitize(evidence)

    def verify_fix(self, hub_id: str, incident_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            incident = self._mutable_incident(hub_id, incident_id)
            evidence_index = self._read_evidence_index(hub_id, incident_id)
            current = self._incident_source_current(hub_id, incident)
            passed_evidence = _valid_passed_evidence_for_incident(evidence_index, incident)
            result = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "hub_id": hub_id,
                "incident_id": incident_id,
                "verified_at": now,
                "status": "passed" if current and passed_evidence else "failed",
                "source": {"incident_hash": incident.get("integrity_hash"), "evidence_index_hash": evidence_index.get("integrity_hash")},
                "checks": [
                    {"check_id": "incident_source_current", "status": "passed" if current else "failed", "severity": "blocking"},
                    {"check_id": "required_external_verification_present", "status": "passed" if passed_evidence else "failed", "severity": "blocking"},
                ],
            }
            result["integrity_hash"] = incident_hash(result)
            _write_json(self.result_path(hub_id, incident_id), result)
            if result["status"] == "passed":
                incident["status"] = "verified"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_fix_verified", now=now)
            return _sanitize(result)

    def close_incident(self, hub_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            if incident.get("stale"):
                raise TrustOperationsIncidentStateError("Stale Trust Operations Incident cannot be closed.")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsIncidentStateError("Closeout reason must be at least 8 characters.")
            result = _read_json_default(self.result_path(hub_id, incident_id), default={})
            if incident.get("blocking") or incident.get("severity") in {"critical", "high"}:
                if result.get("status") != "passed":
                    result = self.verify_fix(hub_id, incident_id, now=now)
                if result.get("status") != "passed":
                    raise TrustOperationsIncidentStateError("Blocking/high incident requires passed fix verification before closeout.")
            evidence_index = self._read_evidence_index(hub_id, incident_id)
            source = self._current_source_for_closeout(hub_id, incident)
            checks = [
                {"check_id": "incident_source_current", "status": "passed" if self._incident_source_current(hub_id, incident) else "failed", "severity": "blocking"},
                {"check_id": "required_external_verification_present", "status": "passed" if _valid_passed_evidence_for_incident(evidence_index, incident) else "failed", "severity": "blocking"},
            ]
            if any(item["status"] == "failed" for item in checks):
                raise TrustOperationsIncidentStateError("Incident closeout checks failed.")
            closeout = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "closeout_id": "closeout-000001",
                "incident_id": incident_id,
                "status": "passed",
                "closed_by": sanitize_sensitive_text(str(payload.get("closed_by") or "local-user")[:120]),
                "closed_at": now,
                "reason": reason[:500],
                "source": {
                    "incident_hash": incident.get("integrity_hash"),
                    "remediation_plan_hash": _read_json_default(self.plan_path(hub_id, incident_id), default={}).get("integrity_hash"),
                    "evidence_index_hash": evidence_index.get("integrity_hash"),
                    **source,
                },
                "checks": checks,
            }
            closeout["integrity_hash"] = incident_hash(closeout)
            _write_json(self.closeout_path(hub_id, incident_id), closeout)
            incident["status"] = "closed"
            incident["closeout_report_id"] = closeout["closeout_id"]
            incident["closed_at"] = now
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_closed", now=now)
            self._refresh_board_summary(hub_id, now=now)
            return _sanitize(closeout)

    def archive_incident(self, hub_id: str, incident_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            incident = self.read_incident(hub_id, incident_id)
            if incident.get("status") != "closed":
                raise TrustOperationsIncidentStateError("Only closed incidents can be archived.")
            incident["status"] = "archived"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_archived", now=now)
            self._refresh_board_summary(hub_id, now=now)
            return _sanitize(incident)
