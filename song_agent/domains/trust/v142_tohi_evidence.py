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

TrustOperationsIncidentStateError = _make_deferred_global('TrustOperationsIncidentStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_binding_for_expected_row = _make_deferred_global('_binding_for_expected_row')
_board_summary = _make_deferred_global('_board_summary')
_category = _make_deferred_global('_category')
_component_id_from_check_id = _make_deferred_global('_component_id_from_check_id')
_component_type_from_check_id = _make_deferred_global('_component_type_from_check_id')
_component_type_from_component_id = _make_deferred_global('_component_type_from_component_id')
_evidence_summary = _make_deferred_global('_evidence_summary')
_expected_evidence_rows_for_component = _make_deferred_global('_expected_evidence_rows_for_component')
_failed_binding = _make_deferred_global('_failed_binding')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_is_generic_component_id = _make_deferred_global('_is_generic_component_id')
_mkdir = _make_deferred_global('_mkdir')
_now = _make_deferred_global('_now')
_read_json = _make_deferred_global('_read_json')
_read_json_default = _make_deferred_global('_read_json_default')
_read_jsonl = _make_deferred_global('_read_jsonl')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
check = _make_deferred_global('check')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsIncidentStateError, _append_jsonl, _binding_for_expected_row, _board_summary, _category, _component_id_from_check_id, _component_type_from_check_id, _component_type_from_component_id
    global _evidence_summary, _expected_evidence_rows_for_component, _failed_binding, _file_record, _fs_path, _is_generic_component_id, _mkdir
    global _now, _read_json, _read_json_default, _read_jsonl, _sanitize, _sha256, _walk_files, _write_json
    global _write_readme, _write_zip, _zip_entries, check, entry, item, key, value
    TrustOperationsIncidentStateError = namespace.get('TrustOperationsIncidentStateError', TrustOperationsIncidentStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _binding_for_expected_row = namespace.get('_binding_for_expected_row', _binding_for_expected_row)
    _board_summary = namespace.get('_board_summary', _board_summary)
    _category = namespace.get('_category', _category)
    _component_id_from_check_id = namespace.get('_component_id_from_check_id', _component_id_from_check_id)
    _component_type_from_check_id = namespace.get('_component_type_from_check_id', _component_type_from_check_id)
    _component_type_from_component_id = namespace.get('_component_type_from_component_id', _component_type_from_component_id)
    _evidence_summary = namespace.get('_evidence_summary', _evidence_summary)
    _expected_evidence_rows_for_component = namespace.get('_expected_evidence_rows_for_component', _expected_evidence_rows_for_component)
    _failed_binding = namespace.get('_failed_binding', _failed_binding)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_generic_component_id = namespace.get('_is_generic_component_id', _is_generic_component_id)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _now = namespace.get('_now', _now)
    _read_json = namespace.get('_read_json', _read_json)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    check = namespace.get('check', check)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
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




class TrustOperationsIncidentStoreEvidenceMixin:
    def export_board(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            board = self.read_board(hub_id)
            if board.get("integrity_hash") != incident_hash(board):
                raise TrustOperationsIncidentStateError("Incident Board integrity failed.")
            source = _read_json_default(self.source_snapshot_path(hub_id), default={})
            incidents = self.list_incidents(hub_id, include_archived=True)
            export_dir = self.export_dir(hub_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            events = self._export_events(hub_id)
            plans = self._all_docs(hub_id, "remediation-plan.json")
            results = self._all_docs(hub_id, "remediation-result.json")
            evidence_index = self._aggregate_evidence(hub_id)
            closeout_summary = self._closeout_summary(hub_id)
            report = self._board_report(board, incidents, source, events, evidence_index, closeout_summary, now)
            _write_json(export_dir / "incident-board.json", board)
            _write_json(export_dir / "incident-board-report.json", report)
            _write_json(export_dir / "incident-source-summary.json", source)
            incidents_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incidents": incidents}
            incidents_doc["integrity_hash"] = incident_hash(incidents_doc)
            _write_json(export_dir / "incidents.json", incidents_doc)
            (export_dir / "incident-events.jsonl").write_text("\n".join(json.dumps(_sanitize(event), ensure_ascii=False, sort_keys=True) for event in events) + ("\n" if events else ""), encoding="utf-8")
            plans_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "plans": plans}
            plans_doc["integrity_hash"] = incident_hash(plans_doc)
            results_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "results": results}
            results_doc["integrity_hash"] = incident_hash(results_doc)
            _write_json(export_dir / "remediation-plans.json", plans_doc)
            _write_json(export_dir / "remediation-results.json", results_doc)
            _write_json(export_dir / "evidence-index.json", evidence_index)
            _write_json(export_dir / "closeout-summary.json", closeout_summary)
            _write_readme(export_dir)
            manifest = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Incident Board", "version": __version__},
                "hub_id": hub_id,
                "board_id": board.get("board_id"),
                "generated_at": now,
                "source_hash": source.get("source_hash"),
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-incident-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "integrity": {
                    "board_hash": board.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "incident_events_hash": stable_hash(events),
                    "evidence_index_hash": evidence_index.get("integrity_hash"),
                    "closeout_summary_hash": closeout_summary.get("integrity_hash"),
                },
            }
            manifest["integrity_hash"] = incident_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-incident-manifest.json", manifest)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            export_dir = self.export_dir(hub_id)
            manifest_path = export_dir / "trust-operations-incident-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsIncidentStateError("Trust Operations Incident export is missing.")
            board = self.read_board(hub_id)
            if manifest.get("integrity", {}).get("board_hash") != board.get("integrity_hash"):
                raise TrustOperationsIncidentStateError("Trust Operations Incident export is stale.")
            zip_path = self.zip_path(hub_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = incident_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            return {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "hub_id": hub_id}

    def verify_zip(self, hub_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_hub_incident_verifier import verify_trust_operations_hub_incident_package

        payload = payload or {}
        report = verify_trust_operations_hub_incident_package(
            self.zip_path(hub_id),
            strict=bool(payload.get("strict", False)),
            require_no_open_critical=bool(payload.get("require_no_open_critical", False)),
            require_no_open_blocking=bool(payload.get("require_no_open_blocking", False)),
            require_current_hub=bool(payload.get("require_current_hub", False)),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id), report)
        return report

    def _current_report_id(self, hub_id: str) -> str:
        current = _read_json_default(self.hub_store.current_report_path(hub_id), default={})
        return str(current.get("report_id") or "")

    def _source_summary(self, hub_id: str, report_id: str, docs: dict[str, DomainDocument]) -> DomainDocument:
        export_manifest = _read_json_default(self.hub_store.export_dir(hub_id, report_id) / "trust-operations-hub-manifest.json", default={})
        zip_path = self.hub_store.zip_path(hub_id, report_id)
        verification = _read_json_default(self.hub_store.verification_report_path(hub_id, report_id), default={})
        source = {
            "hub_id": hub_id,
            "hub_report_id": report_id,
            "hub_report_hash": docs["hub_report"].get("integrity_hash"),
            "hub_manifest_hash": export_manifest.get("integrity_hash"),
            "hub_zip_sha256": _sha256(zip_path) if zip_path.exists() else None,
            "hub_zip_size_bytes": os.stat(_fs_path(zip_path)).st_size if zip_path.exists() else None,
            "hub_verification_report_hash": verification_hash(verification) if verification else None,
            "hub_verification_status": verification.get("status") if verification else None,
            "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
            "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
            "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
            "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
            "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
        }
        source["source_hash"] = stable_hash(source)
        return source

    def _incident_candidates(self, hub_id: str, report_id: str, source: DomainDocument, docs: dict[str, DomainDocument], now: str) -> list[DomainDocument]:
        del now
        rows: list[DomainDocument] = []
        for source_type, register_key in (("trust_operations_hub", "blocker_register"), ("trust_operations_hub_delivery", "delivery_blocker_register")):
            for blocker in docs[register_key].get("blockers", []) if isinstance(docs[register_key].get("blockers"), list) else []:
                if not isinstance(blocker, dict):
                    continue
                component_id = str(blocker.get("component_id") or "unknown")
                requirement = str(blocker.get("requirement") or "unknown")
                component_type = _component_type_from_component_id(component_id)
                check_id = str(blocker.get("source_check_id") or requirement)
                fingerprint_payload = {"source_type": source_type, "check_id": check_id, "component_type": component_type, "component_id": component_id, "requirement": requirement}
                fingerprint = stable_hash(fingerprint_payload)
                severity = str(blocker.get("severity") or "high")
                rows.append(
                    {
                        "title": sanitize_sensitive_text(str(blocker.get("message") or f"{component_id} {requirement} is blocked.")[:200]),
                        "description": sanitize_sensitive_text(str(blocker.get("message") or "")[:1000]),
                        "category": _category(requirement, source_type),
                        "severity": severity if severity in {"critical", "high", "medium", "low", "info"} else "high",
                        "blocking": True,
                        "detected_from": {
                            "source_type": source_type,
                            "check_id": check_id,
                            "component_type": component_type,
                            "component_id": component_id,
                            "requirement": requirement,
                            "source_hash": source.get("source_hash"),
                            "hub_report_hash": source.get("hub_report_hash"),
                            "hub_report_id": report_id,
                            "source_fingerprint": fingerprint,
                        },
                    }
                )
        verification = _read_json_default(self.hub_store.verification_report_path(hub_id, report_id), default={})
        for blocker in verification.get("blockers", []) if isinstance(verification.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            check_id = str(blocker.get("check_id") or "hub_verification_blocker")
            component_type = _component_type_from_check_id(check_id)
            component_id = _component_id_from_check_id(component_type, check_id)
            fingerprint_payload = {"source_type": "trust_operations_hub_verifier", "check_id": check_id, "component_type": component_type, "component_id": component_id}
            fingerprint = stable_hash(fingerprint_payload)
            rows.append(
                {
                    "title": sanitize_sensitive_text(str(blocker.get("message") or check_id)[:200]),
                    "description": sanitize_sensitive_text(str(blocker.get("message") or "")[:1000]),
                    "category": "hub_verification_blocker",
                    "severity": "high",
                    "blocking": True,
                    "detected_from": {
                        "source_type": "trust_operations_hub_verifier",
                        "check_id": check_id,
                        "component_type": component_type,
                        "component_id": component_id,
                        "requirement": check_id,
                        "source_hash": source.get("source_hash"),
                        "hub_report_hash": source.get("hub_report_hash"),
                        "hub_report_id": report_id,
                        "source_fingerprint": fingerprint,
                    },
                }
            )
        return rows

    def _write_incident(self, hub_id: str, incident: DomainDocument, *, event_type: str, now: str) -> None:
        incident["integrity_hash"] = incident_hash(incident)
        _write_json(self.incident_path(hub_id, str(incident["incident_id"])), incident)
        self._append_incident_event(hub_id, str(incident["incident_id"]), event_type, {"status": incident.get("status"), "incident_hash": incident["integrity_hash"]}, now=now)

    def _append_incident_event(self, hub_id: str, incident_id: str, event_type: str, payload: DomainDocument, *, now: str) -> None:
        rows = _read_jsonl(self.incident_events_path(hub_id, incident_id))
        event = {"incident_id": incident_id, "event_id": f"{incident_id}-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.incident_events_path(hub_id, incident_id), event)

    def _append_board_event(self, hub_id: str, event_type: str, payload: DomainDocument, *, now: str) -> None:
        rows = _read_jsonl(self.board_events_path(hub_id))
        event = {"event_id": f"tohi-board-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.board_events_path(hub_id), event)

    def _mutable_incident(self, hub_id: str, incident_id: str) -> DomainDocument:
        incident = self.read_incident(hub_id, incident_id)
        if incident.get("status") in {"closed", "archived"}:
            raise TrustOperationsIncidentStateError("Closed or archived incidents are read-only.")
        if incident.get("integrity_hash") != incident_hash(incident):
            raise TrustOperationsIncidentStateError("Trust Operations Incident integrity failed.")
        return incident

    def _read_evidence_index(self, hub_id: str, incident_id: str) -> DomainDocument:
        return _read_json_default(self.evidence_index_path(hub_id, incident_id), default={"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": [], "summary": _evidence_summary({"evidence": []})})

    def _write_evidence_index(self, hub_id: str, incident_id: str) -> DomainDocument:
        rows = []
        for path in sorted(self.evidence_dir(hub_id, incident_id).glob("ev-*.json")):
            rows.append(_read_json(path))
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        _write_json(self.evidence_index_path(hub_id, incident_id), index)
        return index

    def _bind_evidence_to_hub(self, hub_id: str, incident: DomainDocument, report: DomainDocument, component_type: str, component_id: str) -> DomainDocument:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        if not report_id:
            return _failed_binding(component_type, component_id, "hub_report_id_missing")
        try:
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
        except Exception:
            return _failed_binding(component_type, component_id, "hub_report_not_current")
        rows = _expected_evidence_rows_for_component(docs, component_type)
        if not rows:
            return _failed_binding(component_type, component_id, "expected_evidence_missing")
        requested_component_id = str(component_id or "")
        generic_component = _is_generic_component_id(requested_component_id)
        best_binding: DomainDocument | None = None
        best_score = -1
        for row in rows:
            expected_component_id = str(row.get("component_id") or "")
            if requested_component_id and not generic_component and requested_component_id != expected_component_id:
                continue
            binding = _binding_for_expected_row(row, report)
            score = sum(1 for check in binding.get("binding_checks", []) if isinstance(check, dict) and check.get("status") == "passed")
            if score > best_score:
                best_binding = binding
                best_score = score
            if binding.get("binding_status") == "passed":
                return binding
        if best_binding is not None:
            return best_binding
        return _failed_binding(component_type, component_id, "component_id_not_expected")

    def _incident_source_current(self, hub_id: str, incident: DomainDocument) -> bool:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        if not report_id:
            return False
        try:
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
        except Exception:
            return False
        source = self._source_summary(hub_id, report_id, docs)
        return source.get("hub_report_hash") == incident.get("detected_from", {}).get("hub_report_hash")

    def _current_source_for_closeout(self, hub_id: str, incident: DomainDocument) -> DomainDocument:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        docs = self.hub_store._read_report_docs(hub_id, report_id)
        return self._source_summary(hub_id, report_id, docs)

    def _refresh_board_summary(self, hub_id: str, *, now: str) -> None:
        board = self.read_board(hub_id)
        board["summary"] = _board_summary(self.list_incidents(hub_id, include_archived=False))
        board["status"] = "ready_for_closeout" if board["summary"]["open_count"] == 0 and board["summary"]["stale_count"] == 0 else "open"
        board["updated_at"] = now
        board["integrity_hash"] = incident_hash(board)
        _write_json(self.board_path(hub_id), board)

    def _export_events(self, hub_id: str) -> list[DomainDocument]:
        rows: list[DomainDocument] = []
        for incident in self.list_incidents(hub_id, include_archived=True):
            rows.extend(_read_jsonl(self.incident_events_path(hub_id, str(incident.get("incident_id") or ""))))
        return sorted(rows, key=lambda item: str(item.get("event_id") or ""))

    def _all_docs(self, hub_id: str, filename: str) -> list[DomainDocument]:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob(f"*/{filename}")):
            rows.append(_read_json(path))
        return rows

    def _aggregate_evidence(self, hub_id: str) -> DomainDocument:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/evidence/evidence-index.json")):
            index = _read_json(path)
            rows.extend([item for item in index.get("evidence", []) if isinstance(item, dict)])
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        return index

    def _closeout_summary(self, hub_id: str) -> DomainDocument:
        closeouts = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/closeout-report.json")):
            closeouts.append(_read_json(path))
        data = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "closeouts": closeouts, "summary": {"closeout_count": len(closeouts), "passed_count": sum(1 for row in closeouts if row.get("status") == "passed"), "failed_count": sum(1 for row in closeouts if row.get("status") == "failed")}}
        data["integrity_hash"] = incident_hash(data)
        return data

    def _board_report(self, board: DomainDocument, incidents: list[DomainDocument], source: DomainDocument, events: list[DomainDocument], evidence_index: DomainDocument, closeout_summary: DomainDocument, now: str) -> DomainDocument:
        summary = _board_summary(incidents)
        report = {
            "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE,
            "hub_id": board.get("hub_id"),
            "board_id": board.get("board_id"),
            "generated_at": now,
            "status": "passed" if summary["open_count"] == 0 and summary["stale_count"] == 0 else "blocked",
            "summary": summary,
            "source": {
                "board_hash": board.get("integrity_hash"),
                "source_hash": source.get("source_hash"),
                "event_chain_hash": events[-1].get("event_hash") if events else None,
                "evidence_index_hash": evidence_index.get("integrity_hash"),
                "closeout_summary_hash": closeout_summary.get("integrity_hash"),
            },
        }
        report["integrity_hash"] = incident_hash(report)
        return report
