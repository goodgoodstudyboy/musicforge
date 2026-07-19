# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_publication import PublicTrustCenterPublicationStore as PublicTrustCenterPublicationStore, publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_mirror as verify_public_trust_center_publication_mirror, verify_public_trust_center_publication_package as verify_public_trust_center_publication_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE as PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE, PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE as PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE, PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS as PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS, PUBLICATION_MONITORING_PACKAGE_TYPE as PUBLICATION_MONITORING_PACKAGE_TYPE, PUBLICATION_MONITORING_SCHEMA_VERSION as PUBLICATION_MONITORING_SCHEMA_VERSION, PUBLICATION_MONITOR_RUN_PACKAGE_TYPE as PUBLICATION_MONITOR_RUN_PACKAGE_TYPE, PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE as PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE, monitoring_hash as monitoring_hash, monitoring_manifest_hash as monitoring_manifest_hash, verification_hash as verification_hash

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

PUBLICATION_MONITORING_BLOCKED_KEYS = _make_deferred_global('PUBLICATION_MONITORING_BLOCKED_KEYS')
PublicTrustCenterPublicationMonitoringNotFoundError = _make_deferred_global('PublicTrustCenterPublicationMonitoringNotFoundError')
PublicTrustCenterPublicationMonitoringStateError = _make_deferred_global('PublicTrustCenterPublicationMonitoringStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_check_status_map = _make_deferred_global('_check_status_map')
_drift = _make_deferred_global('_drift')
_event = _make_deferred_global('_event')
_event_chain_valid = _make_deferred_global('_event_chain_valid')
_file_record = _make_deferred_global('_file_record')
_incident_from_events = _make_deferred_global('_incident_from_events')
_mkdir = _make_deferred_global('_mkdir')
_overall_severity = _make_deferred_global('_overall_severity')
_publication_state_row = _make_deferred_global('_publication_state_row')
_read_json_default = _make_deferred_global('_read_json_default')
_read_jsonl = _make_deferred_global('_read_jsonl')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global PUBLICATION_MONITORING_BLOCKED_KEYS, PublicTrustCenterPublicationMonitoringNotFoundError, PublicTrustCenterPublicationMonitoringStateError, _append_jsonl, _check_status_map, _drift, _event, _event_chain_valid
    global _file_record, _incident_from_events, _mkdir, _overall_severity, _publication_state_row, _read_json_default, _read_jsonl
    global _safe_id, _sanitize, _walk_files, _write_json, item
    PUBLICATION_MONITORING_BLOCKED_KEYS = namespace.get('PUBLICATION_MONITORING_BLOCKED_KEYS', PUBLICATION_MONITORING_BLOCKED_KEYS)
    PublicTrustCenterPublicationMonitoringNotFoundError = namespace.get('PublicTrustCenterPublicationMonitoringNotFoundError', PublicTrustCenterPublicationMonitoringNotFoundError)
    PublicTrustCenterPublicationMonitoringStateError = namespace.get('PublicTrustCenterPublicationMonitoringStateError', PublicTrustCenterPublicationMonitoringStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _check_status_map = namespace.get('_check_status_map', _check_status_map)
    _drift = namespace.get('_drift', _drift)
    _event = namespace.get('_event', _event)
    _event_chain_valid = namespace.get('_event_chain_valid', _event_chain_valid)
    _file_record = namespace.get('_file_record', _file_record)
    _incident_from_events = namespace.get('_incident_from_events', _incident_from_events)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _overall_severity = namespace.get('_overall_severity', _overall_severity)
    _publication_state_row = namespace.get('_publication_state_row', _publication_state_row)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


PUBLICATION_MONITOR_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitor"
TERMINAL_INCIDENT_STATUSES = {"resolved", "waived"}
BLOCKING_DRIFT_SEVERITIES = {"critical", "high"}




class PublicTrustCenterPublicationMonitoringStoreEvidenceMixin:
    def _build_probe_results(
        self,
        center_id: str,
        channel_id: str,
        monitor_id: str,
        run_id: str,
        publication_id: str,
        publication_zip: Path,
        mirror_dir: Path,
        channel_state: DomainDocument,
        publication_verification: DomainDocument,
        mirror_verification: DomainDocument,
        now: str,
    ) -> DomainDocument:
        state_row = _publication_state_row(channel_state, publication_id)
        probes = [
            {
                "probe_id": "probe-publication-zip",
                "target_type": "publication_zip",
                "status": "passed" if publication_verification.get("status") == "passed" else "failed",
                "path_hint": publication_zip.name,
                "zip_sha256": publication_verification.get("zip_sha256"),
                "manifest_hash": publication_verification.get("manifest_hash"),
                "report_hash": state_row.get("report_hash"),
                "verification_report_hash": verification_hash(publication_verification),
                "checks": _check_status_map(publication_verification),
            },
            {
                "probe_id": "probe-mirror",
                "target_type": "mirror_dir",
                "status": "passed" if mirror_verification.get("status") in {"passed", "skipped"} else "failed",
                "path_hint": mirror_dir.name,
                "manifest_hash": mirror_verification.get("manifest_hash"),
                "verification_report_hash": verification_hash(mirror_verification),
                "checks": _check_status_map(mirror_verification),
            },
            {
                "probe_id": "probe-channel-state",
                "target_type": "channel_state",
                "status": "passed" if channel_state and state_row else "failed",
                "latest_event_hash": channel_state.get("latest_event_hash") if isinstance(channel_state, dict) else None,
                "channel_state_hash": publication_channel_state_hash(channel_state) if channel_state else None,
                "publication_status": state_row.get("status"),
                "publication_row": state_row,
            },
        ]
        data = {
            "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
            "package_type": PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE,
            "run_id": run_id,
            "monitor_id": monitor_id,
            "center_id": center_id,
            "channel_id": channel_id,
            "publication_id": publication_id,
            "generated_at": now,
            "probes": probes,
            "summary": {
                "publication_zip_sha256": publication_verification.get("zip_sha256"),
                "publication_manifest_hash": publication_verification.get("manifest_hash"),
                "publication_source_hash": state_row.get("source_hash"),
                "publication_report_hash": state_row.get("report_hash"),
                "mirror_manifest_hash": mirror_verification.get("manifest_hash"),
                "probe_count": len(probes),
                "failed_probe_count": sum(1 for item in probes if item.get("status") == "failed"),
            },
        }
        data["integrity_hash"] = monitoring_hash(data)
        return data

    def _build_drift_report(
        self,
        monitor: DomainDocument,
        probe_results: DomainDocument,
        channel_state: DomainDocument,
        publication_verification: DomainDocument,
        mirror_verification: DomainDocument,
        now: str,
    ) -> DomainDocument:
        publication_id = str(probe_results.get("publication_id") or "")
        state_row = _publication_state_row(channel_state, publication_id)
        drifts: list[DomainDocument] = []
        if not channel_state:
            drifts.append(_drift("channel_state_missing", "critical", "Publication channel state is missing."))
        elif not state_row:
            drifts.append(_drift("publication_missing_from_state", "critical", "Publication is missing from channel state."))
        else:
            status = str(state_row.get("status") or "")
            if status == "revoked":
                drifts.append(_drift("publication_revoked", "critical", "Publication has been revoked."))
            if status == "superseded":
                drifts.append(_drift("publication_superseded", "critical", "Publication has been superseded."))
        if publication_verification.get("status") != "passed":
            check_ids = [str(item.get("check_id") or "") for item in publication_verification.get("blockers", []) if isinstance(item, dict)]
            drift_type = "publication_verifier_failed"
            if "ptcpub_zip_open" in check_ids:
                drift_type = "publication_zip_missing"
            elif "ptcpub_channel_state_zip_sha256" in check_ids:
                drift_type = "publication_zip_hash_mismatch"
            elif "ptcpub_channel_state_manifest_hash" in check_ids:
                drift_type = "publication_manifest_hash_mismatch"
            drifts.append(_drift(drift_type, "critical", "Publication ZIP verification failed.", {"blockers": check_ids[:8]}))
        if mirror_verification.get("status") not in {"passed", "skipped"}:
            check_ids = [str(item.get("check_id") or "") for item in mirror_verification.get("blockers", []) if isinstance(item, dict)]
            drift_type = "mirror_verifier_failed"
            if "ptcpub_mirror_open" in check_ids:
                drift_type = "mirror_missing"
            elif "ptcpub_zip_required_entries" in check_ids:
                drift_type = "mirror_file_missing"
            elif "ptcpub_manifest_file_hashes" in check_ids:
                drift_type = "mirror_file_hash_mismatch"
            elif "ptcpub_zip_allowed_entries" in check_ids:
                drift_type = "mirror_extra_file"
            elif "ptcpub_html_safe" in check_ids:
                drift_type = "mirror_html_unsafe"
            drifts.append(_drift(drift_type, "critical", "Publication mirror verification failed.", {"blockers": check_ids[:8]}))
        severity = _overall_severity(drifts)
        data = {
            "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
            "package_type": PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE,
            "run_id": probe_results.get("run_id"),
            "monitor_id": probe_results.get("monitor_id"),
            "center_id": probe_results.get("center_id"),
            "channel_id": probe_results.get("channel_id"),
            "publication_id": publication_id,
            "generated_at": now,
            "status": "failed" if severity in {"critical", "high"} else "warning" if severity == "warning" else "passed",
            "severity": severity,
            "summary": {
                "drift_count": len(drifts),
                "critical_count": sum(1 for item in drifts if item.get("severity") == "critical"),
                "high_count": sum(1 for item in drifts if item.get("severity") == "high"),
                "warning_count": sum(1 for item in drifts if item.get("severity") == "warning"),
            },
            "drifts": drifts,
            "source": {
                "monitor_hash": monitor.get("integrity_hash"),
                "probe_results_hash": probe_results.get("integrity_hash"),
                "channel_state_hash": publication_channel_state_hash(channel_state) if channel_state else None,
                "channel_state_latest_event_hash": channel_state.get("latest_event_hash") if isinstance(channel_state, dict) else None,
                "publication_zip_sha256": (probe_results.get("summary") or {}).get("publication_zip_sha256"),
                "publication_source_hash": (probe_results.get("summary") or {}).get("publication_source_hash"),
                "mirror_manifest_hash": (probe_results.get("summary") or {}).get("mirror_manifest_hash"),
            },
        }
        data["integrity_hash"] = monitoring_hash(data)
        return data

    def _sync_incidents(self, center_id: str, channel_id: str, monitor_id: str, publication_id: str, drift_report: DomainDocument, probe_results: DomainDocument, channel_state: DomainDocument, now: str) -> list[DomainDocument]:
        incidents: list[DomainDocument] = []
        for drift in drift_report.get("drifts", []) if isinstance(drift_report.get("drifts"), list) else []:
            if not isinstance(drift, dict):
                continue
            severity = str(drift.get("severity") or "")
            if severity not in BLOCKING_DRIFT_SEVERITIES:
                continue
            issue_type = str(drift.get("drift_type") or "monitoring_drift")
            incident_id = "ptc-pub-inc-" + stable_hash({"monitor_id": monitor_id, "publication_id": publication_id, "issue_type": issue_type})[:12]
            events = _read_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id))
            current = _incident_from_events(center_id, channel_id, monitor_id, incident_id, events)
            if current.get("status") in TERMINAL_INCIDENT_STATUSES and issue_type != current.get("issue_type"):
                continue
            payload = {
                "run_id": drift_report.get("run_id"),
                "issue_type": issue_type,
                "severity": severity,
                "drift_report_hash": drift_report.get("integrity_hash"),
                "probe_results_hash": probe_results.get("integrity_hash"),
                "channel_state_latest_event_hash": channel_state.get("latest_event_hash") if isinstance(channel_state, dict) else None,
            }
            if not current:
                self._append_incident_event(center_id, channel_id, monitor_id, incident_id, "opened", payload, now=now)
            elif current.get("status") != "open":
                self._append_incident_event(center_id, channel_id, monitor_id, incident_id, "reopened", payload, now=now)
            else:
                self._append_incident_event(center_id, channel_id, monitor_id, incident_id, "note_added", payload, now=now)
            incident = self._rebuild_incident(center_id, channel_id, monitor_id, incident_id, publication_id, now)
            incidents.append(incident)
        if not incidents:
            for incident in self.list_incidents(center_id, channel_id, monitor_id):
                incidents.append(incident)
        return incidents

    def list_incidents(self, center_id: str, channel_id: str, monitor_id: str) -> list[DomainDocument]:
        root = self.incidents_dir(center_id, channel_id, monitor_id)
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("*/incident.json")):
            incident = _read_json_default(path, default={})
            if incident:
                rows.append(_sanitize(incident))
        return rows

    def _incident_report(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, publication_id: str, incidents: list[DomainDocument], now: str) -> DomainDocument:
        rows = sorted(incidents, key=lambda item: str(item.get("incident_id") or ""))
        data = {
            "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
            "package_type": PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE,
            "run_id": run_id,
            "monitor_id": monitor_id,
            "center_id": center_id,
            "channel_id": channel_id,
            "publication_id": publication_id,
            "generated_at": now,
            "incidents": rows,
            "summary": {
                "incident_count": len(rows),
                "open_count": sum(1 for item in rows if item.get("status") == "open"),
                "critical_count": sum(1 for item in rows if item.get("status") == "open" and item.get("severity") == "critical"),
                "waived_count": sum(1 for item in rows if item.get("status") == "waived"),
                "resolved_count": sum(1 for item in rows if item.get("status") == "resolved"),
            },
        }
        data["integrity_hash"] = monitoring_hash(data)
        return data

    def _incident_transition(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, event_type: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            if not self.incident_events_path(center_id, channel_id, monitor_id, incident_id).exists():
                raise PublicTrustCenterPublicationMonitoringNotFoundError("Publication monitoring incident not found.")
            self._append_incident_event(center_id, channel_id, monitor_id, incident_id, event_type, payload, now=now)
            incident = self._rebuild_incident(center_id, channel_id, monitor_id, incident_id, None, now)
            return _sanitize(incident)

    def _incident_events_for_report(self, center_id: str, channel_id: str, monitor_id: str, incident_report: DomainDocument) -> list[DomainDocument]:
        rows: list[DomainDocument] = []
        seen: set[str] = set()
        for incident in incident_report.get("incidents", []) if isinstance(incident_report.get("incidents"), list) else []:
            if not isinstance(incident, dict):
                continue
            incident_id = _safe_id(str(incident.get("incident_id") or ""))
            if not incident_id or incident_id in seen:
                continue
            seen.add(incident_id)
            events = _read_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id))
            rows.extend(events)
        return sorted(rows, key=lambda item: (str(item.get("incident_id") or ""), int(item.get("sequence") or 0), str(item.get("event_id") or "")))

    def _append_monitor_event(self, center_id: str, channel_id: str, monitor_id: str, event_type: str, payload: DomainDocument, *, now: str) -> DomainDocument:
        events = _read_jsonl(self.events_path(center_id, channel_id, monitor_id))
        event = _event(str(event_type), payload, events[-1].get("event_hash") if events else None, now, "ptc-pub-mon-event", len(events) + 1)
        _append_jsonl(self.events_path(center_id, channel_id, monitor_id), event)
        return event

    def _append_incident_event(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, event_type: str, payload: DomainDocument, *, now: str) -> DomainDocument:
        events = _read_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id))
        event = _event(str(event_type), sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS), events[-1].get("event_hash") if events else None, now, "ptc-pub-inc-event", len(events) + 1)
        event["incident_id"] = incident_id
        _append_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id), event)
        return event

    def _rebuild_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, publication_id: str | None, now: str) -> DomainDocument:
        events = _read_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id))
        incident = _incident_from_events(center_id, channel_id, monitor_id, incident_id, events)
        if not incident:
            raise PublicTrustCenterPublicationMonitoringNotFoundError("Publication monitoring incident not found.")
        if publication_id:
            incident["publication_id"] = publication_id
        incident["updated_at"] = now
        incident["event_count"] = len(events)
        incident["latest_event_hash"] = events[-1].get("event_hash") if events else None
        incident["event_chain_valid"] = _event_chain_valid(events)
        incident["integrity_hash"] = monitoring_hash(incident)
        _mkdir(self.incident_dir(center_id, channel_id, monitor_id, incident_id))
        _write_json(self.incident_path(center_id, channel_id, monitor_id, incident_id), incident)
        return incident

    def _read_run(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> DomainDocument:
        run = _read_json_default(self.run_path(center_id, channel_id, monitor_id, run_id), default={})
        if not run:
            raise PublicTrustCenterPublicationMonitoringNotFoundError("Publication monitoring run not found.")
        return run

    def _assert_run_artifacts_current(self, run: DomainDocument, probe_results: DomainDocument, drift_report: DomainDocument, incident_report: DomainDocument, channel_state_snapshot: DomainDocument) -> None:
        if run.get("integrity_hash") != monitoring_hash(run):
            raise PublicTrustCenterPublicationMonitoringStateError("Monitoring run integrity failed.")
        if probe_results.get("integrity_hash") != monitoring_hash(probe_results):
            raise PublicTrustCenterPublicationMonitoringStateError("Probe results integrity failed.")
        if drift_report.get("integrity_hash") != monitoring_hash(drift_report):
            raise PublicTrustCenterPublicationMonitoringStateError("Drift report integrity failed.")
        if incident_report.get("integrity_hash") != monitoring_hash(incident_report):
            raise PublicTrustCenterPublicationMonitoringStateError("Incident report integrity failed.")
        if run.get("source", {}).get("probe_results_hash") != probe_results.get("integrity_hash") or run.get("source", {}).get("drift_report_hash") != drift_report.get("integrity_hash") or run.get("source", {}).get("incident_report_hash") != incident_report.get("integrity_hash"):
            raise PublicTrustCenterPublicationMonitoringStateError("Monitoring run source references are stale.")
        if channel_state_snapshot and run.get("source", {}).get("channel_state_snapshot_hash") != publication_channel_state_hash(channel_state_snapshot):
            raise PublicTrustCenterPublicationMonitoringStateError("Monitoring channel state snapshot is stale.")

    def _file_index(self, export_dir: Path) -> DomainDocument:
        data = {"schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION, "source_hash": stable_hash([_file_record(export_dir, path) for path in _walk_files(export_dir)]), "files": [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "file-index.json"]}
        data["integrity_hash"] = monitoring_hash(data)
        return data
