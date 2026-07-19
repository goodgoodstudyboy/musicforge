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

PublicTrustCenterPublicationMonitoringNotFoundError = _make_deferred_global('PublicTrustCenterPublicationMonitoringNotFoundError')
PublicTrustCenterPublicationMonitoringStateError = _make_deferred_global('PublicTrustCenterPublicationMonitoringStateError')
_checksum_json = _make_deferred_global('_checksum_json')
_default_drift_policy = _make_deferred_global('_default_drift_policy')
_default_requirements = _make_deferred_global('_default_requirements')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_mkdir = _make_deferred_global('_mkdir')
_next_id = _make_deferred_global('_next_id')
_public_path_hint = _make_deferred_global('_public_path_hint')
_read_json_default = _make_deferred_global('_read_json_default')
_run_status = _make_deferred_global('_run_status')
_safe_copy = _make_deferred_global('_safe_copy')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_walk_files = _make_deferred_global('_walk_files')
_write_json = _make_deferred_global('_write_json')
_write_jsonl = _make_deferred_global('_write_jsonl')
_write_readme = _make_deferred_global('_write_readme')
_write_sha256sums = _make_deferred_global('_write_sha256sums')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterPublicationMonitoringNotFoundError, PublicTrustCenterPublicationMonitoringStateError, _checksum_json, _default_drift_policy, _default_requirements, _ensure_within, _file_record, _fs_path
    global _mkdir, _next_id, _public_path_hint, _read_json_default, _run_status, _safe_copy, _safe_id
    global _sanitize, _sha256, _walk_files, _write_json, _write_jsonl, _write_readme, _write_sha256sums, _write_zip
    global _zip_entries, entry, item, key
    PublicTrustCenterPublicationMonitoringNotFoundError = namespace.get('PublicTrustCenterPublicationMonitoringNotFoundError', PublicTrustCenterPublicationMonitoringNotFoundError)
    PublicTrustCenterPublicationMonitoringStateError = namespace.get('PublicTrustCenterPublicationMonitoringStateError', PublicTrustCenterPublicationMonitoringStateError)
    _checksum_json = namespace.get('_checksum_json', _checksum_json)
    _default_drift_policy = namespace.get('_default_drift_policy', _default_drift_policy)
    _default_requirements = namespace.get('_default_requirements', _default_requirements)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _next_id = namespace.get('_next_id', _next_id)
    _public_path_hint = namespace.get('_public_path_hint', _public_path_hint)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _run_status = namespace.get('_run_status', _run_status)
    _safe_copy = namespace.get('_safe_copy', _safe_copy)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _walk_files = namespace.get('_walk_files', _walk_files)
    _write_json = namespace.get('_write_json', _write_json)
    _write_jsonl = namespace.get('_write_jsonl', _write_jsonl)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_sha256sums = namespace.get('_write_sha256sums', _write_sha256sums)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


PUBLICATION_MONITOR_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitor"
TERMINAL_INCIDENT_STATUSES = {"resolved", "waived"}
BLOCKING_DRIFT_SEVERITIES = {"critical", "high"}




class PublicTrustCenterPublicationMonitoringStoreReadinessMixin:
    def root_dir(self, center_id: str, channel_id: str) -> Path:
        return self.publication_store.channel_dir(center_id, channel_id) / "monitoring"

    def monitors_dir(self, center_id: str, channel_id: str) -> Path:
        return self.root_dir(center_id, channel_id) / "monitors"

    def monitor_dir(self, center_id: str, channel_id: str, monitor_id: str) -> Path:
        return self.monitors_dir(center_id, channel_id) / _safe_id(monitor_id)

    def monitor_path(self, center_id: str, channel_id: str, monitor_id: str) -> Path:
        return self.monitor_dir(center_id, channel_id, monitor_id) / "monitor.json"

    def events_path(self, center_id: str, channel_id: str, monitor_id: str) -> Path:
        return self.monitor_dir(center_id, channel_id, monitor_id) / "events.jsonl"

    def runs_dir(self, center_id: str, channel_id: str, monitor_id: str) -> Path:
        return self.monitor_dir(center_id, channel_id, monitor_id) / "runs"

    def run_dir(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.runs_dir(center_id, channel_id, monitor_id) / _safe_id(run_id)

    def run_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "monitor-run.json"

    def probe_results_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "probe-results.json"

    def drift_report_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "drift-report.json"

    def incident_report_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "incident-report.json"

    def channel_state_snapshot_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "channel-state-snapshot.json"

    def verification_reports_dir(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "verification-reports"

    def publication_verification_report_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.verification_reports_dir(center_id, channel_id, monitor_id, run_id) / "publication-verification-report.json"

    def mirror_verification_report_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.verification_reports_dir(center_id, channel_id, monitor_id, run_id) / "mirror-verification-report.json"

    def export_dir(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "export"

    def zip_path(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> Path:
        return self.run_dir(center_id, channel_id, monitor_id, run_id) / "public-trust-center-publication-monitoring.zip"

    def incidents_dir(self, center_id: str, channel_id: str, monitor_id: str) -> Path:
        return self.monitor_dir(center_id, channel_id, monitor_id) / "incidents"

    def incident_dir(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str) -> Path:
        return self.incidents_dir(center_id, channel_id, monitor_id) / _safe_id(incident_id)

    def incident_path(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str) -> Path:
        return self.incident_dir(center_id, channel_id, monitor_id, incident_id) / "incident.json"

    def incident_events_path(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str) -> Path:
        return self.incident_dir(center_id, channel_id, monitor_id, incident_id) / "incident-events.jsonl"

    def create_monitor(self, center_id: str, channel_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            self.publication_store.read_channel(center_id, channel_id)
            monitor_id = _safe_id(str(payload.get("monitor_id") or _next_id(self.monitors_dir(center_id, channel_id), "ptc-pub-mon")))
            selector = _as_document(payload.get("publication_selector"))
            selector_mode = str(selector.get("mode") or ("pinned" if payload.get("publication_id") else "current"))
            if selector_mode not in {"current", "pinned"}:
                raise PublicTrustCenterPublicationMonitoringStateError("Publication monitor selector mode must be current or pinned.")
            requirements = _default_requirements()
            if isinstance(payload.get("requirements"), dict):
                requirements.update({key: bool(value) for key, value in payload["requirements"].items() if key in requirements})
            monitor = {
                "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
                "package_type": PUBLICATION_MONITOR_PACKAGE_TYPE,
                "monitor_id": monitor_id,
                "center_id": center_id,
                "channel_id": channel_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Public Trust Center Publication Monitor")[:160]),
                "created_at": now,
                "updated_at": now,
                "status": "active",
                "publication_selector": {
                    "mode": selector_mode,
                    "publication_id": str(selector.get("publication_id") or payload.get("publication_id") or "") or None,
                },
                "targets": {
                    "publication_zip": bool((_as_document(payload.get("targets"))).get("publication_zip", True)),
                    "mirror_dir": bool((_as_document(payload.get("targets"))).get("mirror_dir", True)),
                    "channel_state": True,
                },
                "mirror": {"kind": "local_dir", "path_hint": _public_path_hint(payload.get("mirror_dir"))},
                "requirements": requirements,
                "drift_policy": _default_drift_policy(),
                "notes": sanitize_sensitive_text(str(payload.get("notes") or "")[:1000]),
            }
            monitor["integrity_hash"] = monitoring_hash(monitor)
            _mkdir(self.monitor_dir(center_id, channel_id, monitor_id))
            _write_json(self.monitor_path(center_id, channel_id, monitor_id), monitor)
            self._append_monitor_event(center_id, channel_id, monitor_id, "monitor_created", {"monitor_hash": monitor["integrity_hash"]}, now=now)
            return _sanitize(monitor)

    def read_monitor(self, center_id: str, channel_id: str, monitor_id: str) -> DomainDocument:
        value = _read_json_default(self.monitor_path(center_id, channel_id, monitor_id), default={})
        if not value:
            raise PublicTrustCenterPublicationMonitoringNotFoundError("Public Trust Center publication monitor not found.")
        return value

    def list_monitors(self, center_id: str, channel_id: str, include_inactive: bool = False) -> list[DomainDocument]:
        root = self.monitors_dir(center_id, channel_id)
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("*/monitor.json")):
            monitor = _read_json_default(path, default={})
            if not monitor:
                continue
            if not include_inactive and monitor.get("status") != "active":
                continue
            rows.append(_sanitize(monitor))
        return rows

    def list_runs(self, center_id: str, channel_id: str, monitor_id: str) -> list[DomainDocument]:
        root = self.runs_dir(center_id, channel_id, monitor_id)
        if not root.exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("*/monitor-run.json")):
            run = _read_json_default(path, default={})
            if run:
                rows.append(_sanitize(run))
        return rows

    def run_monitor(self, center_id: str, channel_id: str, monitor_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            monitor = self.read_monitor(center_id, channel_id, monitor_id)
            publication_id = self._resolve_publication_id(center_id, channel_id, monitor, payload)
            run_id = _safe_id(str(payload.get("run_id") or _next_id(self.runs_dir(center_id, channel_id, monitor_id), "ptc-pub-mon-run")))
            run_dir = self.run_dir(center_id, channel_id, monitor_id, run_id)
            _mkdir(run_dir)
            _mkdir(self.verification_reports_dir(center_id, channel_id, monitor_id, run_id))
            channel_state_path = Path(payload.get("publication_channel_state_path") or self.publication_store.channel_state_path(center_id, channel_id))
            channel_state = _read_json_default(channel_state_path, default={})
            if channel_state:
                _write_json(self.channel_state_snapshot_path(center_id, channel_id, monitor_id, run_id), channel_state)
            publication_zip = self.publication_store.zip_path(center_id, channel_id, publication_id)
            mirror_dir = Path(payload.get("mirror_dir") or self.publication_store.export_dir(center_id, channel_id, publication_id))
            requirements = _document_or(monitor.get("requirements"), _default_requirements())
            targets = _as_document(monitor.get("targets"))
            publication_verification = verify_public_trust_center_publication_package(
                publication_zip,
                strict=True,
                deep=bool(payload.get("deep", False)),
                require_ready=bool(requirements.get("require_ready", True)),
                require_acceptance_board_signoff=bool(requirements.get("require_acceptance_board_signoff", True)),
                require_anchor_current=bool(requirements.get("require_anchor_current", True)),
                require_no_revoked=bool(requirements.get("require_no_revoked", True) or requirements.get("require_current", True)),
                publication_channel_state_path=channel_state_path,
            )
            publication_report_path = self.publication_verification_report_path(center_id, channel_id, monitor_id, run_id)
            _mkdir(publication_report_path.parent)
            _write_json(publication_report_path, publication_verification)
            publication_verification = _read_json_default(publication_report_path, default=publication_verification)
            mirror_verification: DomainDocument = {"status": "skipped", "summary": {"reason": "mirror target disabled"}}
            if bool(targets.get("mirror_dir", True)):
                mirror_verification = verify_public_trust_center_publication_mirror(
                    mirror_dir,
                    strict=True,
                    require_ready=bool(requirements.get("require_ready", True)),
                    require_acceptance_board_signoff=bool(requirements.get("require_acceptance_board_signoff", True)),
                    require_anchor_current=bool(requirements.get("require_anchor_current", True)),
                    require_no_revoked=bool(requirements.get("require_no_revoked", True) or requirements.get("require_current", True)),
                    publication_channel_state_path=channel_state_path,
                )
                mirror_report_path = self.mirror_verification_report_path(center_id, channel_id, monitor_id, run_id)
                _mkdir(mirror_report_path.parent)
                _write_json(mirror_report_path, mirror_verification)
                mirror_verification = _read_json_default(mirror_report_path, default=mirror_verification)
            probe_results = self._build_probe_results(
                center_id,
                channel_id,
                monitor_id,
                run_id,
                publication_id,
                publication_zip,
                mirror_dir,
                channel_state,
                publication_verification,
                mirror_verification,
                now,
            )
            drift_report = self._build_drift_report(monitor, probe_results, channel_state, publication_verification, mirror_verification, now)
            incidents = self._sync_incidents(center_id, channel_id, monitor_id, publication_id, drift_report, probe_results, channel_state, now)
            incident_report = self._incident_report(center_id, channel_id, monitor_id, run_id, publication_id, incidents, now)
            run = {
                "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
                "package_type": PUBLICATION_MONITOR_RUN_PACKAGE_TYPE,
                "run_id": run_id,
                "monitor_id": monitor_id,
                "center_id": center_id,
                "channel_id": channel_id,
                "publication_id": publication_id,
                "generated_at": now,
                "status": _run_status(drift_report, incident_report),
                "source": {
                    "monitor_hash": monitor.get("integrity_hash"),
                    "probe_results_hash": probe_results.get("integrity_hash"),
                    "drift_report_hash": drift_report.get("integrity_hash"),
                    "incident_report_hash": incident_report.get("integrity_hash"),
                    "channel_state_snapshot_hash": publication_channel_state_hash(channel_state) if channel_state else None,
                },
                "summary": {
                    "drift_status": drift_report.get("status"),
                    "drift_count": (drift_report.get("summary") or {}).get("drift_count"),
                    "open_incidents": (incident_report.get("summary") or {}).get("open_count"),
                    "critical_incidents": (incident_report.get("summary") or {}).get("critical_count"),
                },
            }
            run["integrity_hash"] = monitoring_hash(run)
            _write_json(self.probe_results_path(center_id, channel_id, monitor_id, run_id), probe_results)
            _write_json(self.drift_report_path(center_id, channel_id, monitor_id, run_id), drift_report)
            _write_json(self.incident_report_path(center_id, channel_id, monitor_id, run_id), incident_report)
            _write_json(self.run_path(center_id, channel_id, monitor_id, run_id), run)
            self._append_monitor_event(center_id, channel_id, monitor_id, "monitor_run_completed", {"run_id": run_id, "status": run.get("status"), "drift_report_hash": drift_report.get("integrity_hash")}, now=now)
            return {"monitor_run": _sanitize(run), "probe_results": _sanitize(probe_results), "drift_report": _sanitize(drift_report), "incident_report": _sanitize(incident_report)}

    def acknowledge_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "acknowledged", payload or {}, now=now)

    def resolve_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        note = str(payload.get("resolution_note") or payload.get("reason") or "").strip()
        if len(note) < 8:
            raise PublicTrustCenterPublicationMonitoringStateError("Incident resolution_note must be at least 8 characters.")
        payload["resolution_note"] = note
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "resolved", payload, now=now)

    def waive_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        reason = str(payload.get("waiver_reason") or payload.get("reason") or "").strip()
        if len(reason) < 8:
            raise PublicTrustCenterPublicationMonitoringStateError("Incident waiver_reason must be at least 8 characters.")
        payload["waiver_reason"] = reason
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "waived", payload, now=now)

    def reopen_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "reopened", payload or {}, now=now)

    def export_monitoring_run(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            run = self._read_run(center_id, channel_id, monitor_id, run_id)
            probe_results = _read_json_default(self.probe_results_path(center_id, channel_id, monitor_id, run_id), default={})
            drift_report = _read_json_default(self.drift_report_path(center_id, channel_id, monitor_id, run_id), default={})
            incident_report = _read_json_default(self.incident_report_path(center_id, channel_id, monitor_id, run_id), default={})
            incident_events = self._incident_events_for_report(center_id, channel_id, monitor_id, incident_report)
            channel_state_snapshot = _read_json_default(self.channel_state_snapshot_path(center_id, channel_id, monitor_id, run_id), default={})
            self._assert_run_artifacts_current(run, probe_results, drift_report, incident_report, channel_state_snapshot)
            export_dir = self.export_dir(center_id, channel_id, monitor_id, run_id).resolve()
            _ensure_within(self.run_dir(center_id, channel_id, monitor_id, run_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            _mkdir(export_dir / "verification-reports")
            _mkdir(export_dir / "checksum")
            _write_json(export_dir / "monitor-run.json", run)
            _write_json(export_dir / "probe-results.json", probe_results)
            _write_json(export_dir / "drift-report.json", drift_report)
            _write_json(export_dir / "incident-report.json", incident_report)
            _write_jsonl(export_dir / "incident-events.jsonl", incident_events)
            _write_json(export_dir / "channel-state-snapshot.json", channel_state_snapshot)
            _safe_copy(self.publication_verification_report_path(center_id, channel_id, monitor_id, run_id), export_dir / "verification-reports" / "publication-verification-report.json", export_dir)
            mirror_report_path = self.mirror_verification_report_path(center_id, channel_id, monitor_id, run_id)
            if os.path.exists(_fs_path(mirror_report_path)):
                _safe_copy(mirror_report_path, export_dir / "verification-reports" / "mirror-verification-report.json", export_dir)
            else:
                _write_json(export_dir / "verification-reports" / "mirror-verification-report.json", {"status": "skipped", "summary": {"reason": "mirror target disabled"}})
            _write_readme(export_dir)
            file_index = self._file_index(export_dir)
            _write_json(export_dir / "file-index.json", file_index)
            checksum_json = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum_json)
            _write_sha256sums(export_dir, checksum_json)
            source = {
                "monitor_hash": self.read_monitor(center_id, channel_id, monitor_id).get("integrity_hash"),
                "monitor_run_hash": run.get("integrity_hash"),
                "probe_results_hash": probe_results.get("integrity_hash"),
                "drift_report_hash": drift_report.get("integrity_hash"),
                "incident_report_hash": incident_report.get("integrity_hash"),
                "incident_events_hash": stable_hash(incident_events),
                "channel_state_snapshot_hash": publication_channel_state_hash(channel_state_snapshot) if channel_state_snapshot else None,
                "publication_zip_sha256": (probe_results.get("summary") or {}).get("publication_zip_sha256"),
                "publication_manifest_hash": (probe_results.get("summary") or {}).get("publication_manifest_hash"),
                "publication_source_hash": (probe_results.get("summary") or {}).get("publication_source_hash"),
                "publication_report_hash": (probe_results.get("summary") or {}).get("publication_report_hash"),
                "mirror_manifest_hash": (probe_results.get("summary") or {}).get("mirror_manifest_hash"),
                "channel_state_latest_event_hash": channel_state_snapshot.get("latest_event_hash") if isinstance(channel_state_snapshot, dict) else None,
            }
            files = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "monitoring-manifest.json"]
            manifest = {
                "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
                "package_type": PUBLICATION_MONITORING_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Publication Monitoring", "version": __version__},
                "center_id": center_id,
                "channel_id": channel_id,
                "monitor_id": monitor_id,
                "run_id": run_id,
                "publication_id": run.get("publication_id"),
                "generated_at": now,
                "status": run.get("status"),
                "source": source,
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = monitoring_manifest_hash(manifest)
            _write_json(export_dir / "monitoring-manifest.json", manifest)
            self._append_monitor_event(center_id, channel_id, monitor_id, "monitoring_exported", {"run_id": run_id, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_monitoring_zip(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(center_id, channel_id, monitor_id, run_id).resolve()
            manifest = _read_json_default(export_dir / "monitoring-manifest.json", default={})
            if not manifest:
                raise PublicTrustCenterPublicationMonitoringStateError("Monitoring export is missing. Export before ZIP.")
            run = self._read_run(center_id, channel_id, monitor_id, run_id)
            if manifest.get("source", {}).get("monitor_run_hash") != run.get("integrity_hash"):
                raise PublicTrustCenterPublicationMonitoringStateError("Monitoring export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id, channel_id, monitor_id, run_id).resolve()
            _ensure_within(self.run_dir(center_id, channel_id, monitor_id, run_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = monitoring_manifest_hash(manifest)
            _write_json(export_dir / "monitoring-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "run_id": run_id, "monitor_id": monitor_id}
            self._append_monitor_event(center_id, channel_id, monitor_id, "monitoring_zip_built", {"run_id": run_id, "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(info)

    def verify_monitoring_zip(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_publication_monitoring_verifier import verify_public_trust_center_publication_monitoring_package, write_public_trust_center_publication_monitoring_verification_report

        payload = payload or {}
        report = verify_public_trust_center_publication_monitoring_package(
            self.zip_path(center_id, channel_id, monitor_id, run_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", False)),
            require_no_revoked=bool(payload.get("require_no_revoked", False)),
            require_ready=bool(payload.get("require_ready", False)),
            require_no_drift=bool(payload.get("require_no_drift", False)),
            require_no_open_critical_incidents=bool(payload.get("require_no_open_critical_incidents", False)),
            allow_waived_incidents=bool(payload.get("allow_waived_incidents", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path") or self.publication_store.channel_state_path(center_id, channel_id),
        )
        write_public_trust_center_publication_monitoring_verification_report(report, self.run_dir(center_id, channel_id, monitor_id, run_id) / "monitoring-verification-report.json")
        return report

    def _resolve_publication_id(self, center_id: str, channel_id: str, monitor: DomainDocument, payload: DomainDocument) -> str:
        explicit = str(payload.get("publication_id") or "").strip()
        if explicit and explicit != "current":
            return _safe_id(explicit)
        selector = _as_document(monitor.get("publication_selector"))
        if str(selector.get("mode") or "current") == "pinned" and selector.get("publication_id"):
            return _safe_id(str(selector.get("publication_id")))
        return self.publication_store._current_publication_id(center_id, channel_id)
