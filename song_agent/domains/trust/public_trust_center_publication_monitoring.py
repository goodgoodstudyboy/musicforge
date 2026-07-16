from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.trust.public_trust_center_publication import PublicTrustCenterPublicationStore, publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_mirror, verify_public_trust_center_publication_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE, PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE, PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS, PUBLICATION_MONITORING_PACKAGE_TYPE, PUBLICATION_MONITORING_SCHEMA_VERSION, PUBLICATION_MONITOR_RUN_PACKAGE_TYPE, PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE, monitoring_hash, monitoring_manifest_hash, verification_hash



PUBLICATION_MONITOR_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitor"






PUBLICATION_MONITORING_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
TERMINAL_INCIDENT_STATUSES = {"resolved", "waived"}
BLOCKING_DRIFT_SEVERITIES = {"critical", "high"}


class PublicTrustCenterPublicationMonitoringError(ValueError):
    pass


class PublicTrustCenterPublicationMonitoringNotFoundError(PublicTrustCenterPublicationMonitoringError):
    pass


class PublicTrustCenterPublicationMonitoringStateError(PublicTrustCenterPublicationMonitoringError):
    pass


class PublicTrustCenterPublicationMonitoringStore:
    def __init__(self, *, publication_store: PublicTrustCenterPublicationStore) -> None:
        self.publication_store = publication_store
        self.lock = threading.RLock()

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

    def create_monitor(self, center_id: str, channel_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            self.publication_store.read_channel(center_id, channel_id)
            monitor_id = _safe_id(str(payload.get("monitor_id") or _next_id(self.monitors_dir(center_id, channel_id), "ptc-pub-mon")))
            selector = payload.get("publication_selector") if isinstance(payload.get("publication_selector"), dict) else {}
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
                    "publication_zip": bool((payload.get("targets") if isinstance(payload.get("targets"), dict) else {}).get("publication_zip", True)),
                    "mirror_dir": bool((payload.get("targets") if isinstance(payload.get("targets"), dict) else {}).get("mirror_dir", True)),
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

    def read_monitor(self, center_id: str, channel_id: str, monitor_id: str) -> dict[str, Any]:
        value = _read_json_default(self.monitor_path(center_id, channel_id, monitor_id), default={})
        if not value:
            raise PublicTrustCenterPublicationMonitoringNotFoundError("Public Trust Center publication monitor not found.")
        return value

    def list_monitors(self, center_id: str, channel_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        root = self.monitors_dir(center_id, channel_id)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/monitor.json")):
            monitor = _read_json_default(path, default={})
            if not monitor:
                continue
            if not include_inactive and monitor.get("status") != "active":
                continue
            rows.append(_sanitize(monitor))
        return rows

    def list_runs(self, center_id: str, channel_id: str, monitor_id: str) -> list[dict[str, Any]]:
        root = self.runs_dir(center_id, channel_id, monitor_id)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/monitor-run.json")):
            run = _read_json_default(path, default={})
            if run:
                rows.append(_sanitize(run))
        return rows

    def run_monitor(self, center_id: str, channel_id: str, monitor_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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
            requirements = monitor.get("requirements") if isinstance(monitor.get("requirements"), dict) else _default_requirements()
            targets = monitor.get("targets") if isinstance(monitor.get("targets"), dict) else {}
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
            mirror_verification: dict[str, Any] = {"status": "skipped", "summary": {"reason": "mirror target disabled"}}
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

    def acknowledge_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "acknowledged", payload or {}, now=now)

    def resolve_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        note = str(payload.get("resolution_note") or payload.get("reason") or "").strip()
        if len(note) < 8:
            raise PublicTrustCenterPublicationMonitoringStateError("Incident resolution_note must be at least 8 characters.")
        payload["resolution_note"] = note
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "resolved", payload, now=now)

    def waive_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = str(payload.get("waiver_reason") or payload.get("reason") or "").strip()
        if len(reason) < 8:
            raise PublicTrustCenterPublicationMonitoringStateError("Incident waiver_reason must be at least 8 characters.")
        payload["waiver_reason"] = reason
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "waived", payload, now=now)

    def reopen_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        return self._incident_transition(center_id, channel_id, monitor_id, incident_id, "reopened", payload or {}, now=now)

    def export_monitoring_run(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def build_monitoring_zip(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def verify_monitoring_zip(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def _resolve_publication_id(self, center_id: str, channel_id: str, monitor: ImplementationDocument, payload: ImplementationDocument) -> str:
        explicit = str(payload.get("publication_id") or "").strip()
        if explicit and explicit != "current":
            return _safe_id(explicit)
        selector = monitor.get("publication_selector") if isinstance(monitor.get("publication_selector"), dict) else {}
        if str(selector.get("mode") or "current") == "pinned" and selector.get("publication_id"):
            return _safe_id(str(selector.get("publication_id")))
        return self.publication_store._current_publication_id(center_id, channel_id)

    def _build_probe_results(
        self,
        center_id: str,
        channel_id: str,
        monitor_id: str,
        run_id: str,
        publication_id: str,
        publication_zip: Path,
        mirror_dir: Path,
        channel_state: ImplementationDocument,
        publication_verification: ImplementationDocument,
        mirror_verification: ImplementationDocument,
        now: str,
    ) -> ImplementationDocument:
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
        monitor: ImplementationDocument,
        probe_results: ImplementationDocument,
        channel_state: ImplementationDocument,
        publication_verification: ImplementationDocument,
        mirror_verification: ImplementationDocument,
        now: str,
    ) -> ImplementationDocument:
        publication_id = str(probe_results.get("publication_id") or "")
        state_row = _publication_state_row(channel_state, publication_id)
        drifts: list[dict[str, Any]] = []
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

    def _sync_incidents(self, center_id: str, channel_id: str, monitor_id: str, publication_id: str, drift_report: ImplementationDocument, probe_results: ImplementationDocument, channel_state: ImplementationDocument, now: str) -> list[ImplementationDocument]:
        incidents: list[dict[str, Any]] = []
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

    def list_incidents(self, center_id: str, channel_id: str, monitor_id: str) -> list[dict[str, Any]]:
        root = self.incidents_dir(center_id, channel_id, monitor_id)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/incident.json")):
            incident = _read_json_default(path, default={})
            if incident:
                rows.append(_sanitize(incident))
        return rows

    def _incident_report(self, center_id: str, channel_id: str, monitor_id: str, run_id: str, publication_id: str, incidents: list[ImplementationDocument], now: str) -> ImplementationDocument:
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

    def _incident_transition(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, event_type: str, payload: ImplementationDocument, *, now: str | None = None) -> ImplementationDocument:
        with self.lock:
            now = now or now_iso()
            if not self.incident_events_path(center_id, channel_id, monitor_id, incident_id).exists():
                raise PublicTrustCenterPublicationMonitoringNotFoundError("Publication monitoring incident not found.")
            self._append_incident_event(center_id, channel_id, monitor_id, incident_id, event_type, payload, now=now)
            incident = self._rebuild_incident(center_id, channel_id, monitor_id, incident_id, None, now)
            return _sanitize(incident)

    def _incident_events_for_report(self, center_id: str, channel_id: str, monitor_id: str, incident_report: ImplementationDocument) -> list[ImplementationDocument]:
        rows: list[dict[str, Any]] = []
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

    def _append_monitor_event(self, center_id: str, channel_id: str, monitor_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> ImplementationDocument:
        events = _read_jsonl(self.events_path(center_id, channel_id, monitor_id))
        event = _event(str(event_type), payload, events[-1].get("event_hash") if events else None, now, "ptc-pub-mon-event", len(events) + 1)
        _append_jsonl(self.events_path(center_id, channel_id, monitor_id), event)
        return event

    def _append_incident_event(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> ImplementationDocument:
        events = _read_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id))
        event = _event(str(event_type), sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS), events[-1].get("event_hash") if events else None, now, "ptc-pub-inc-event", len(events) + 1)
        event["incident_id"] = incident_id
        _append_jsonl(self.incident_events_path(center_id, channel_id, monitor_id, incident_id), event)
        return event

    def _rebuild_incident(self, center_id: str, channel_id: str, monitor_id: str, incident_id: str, publication_id: str | None, now: str) -> ImplementationDocument:
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

    def _read_run(self, center_id: str, channel_id: str, monitor_id: str, run_id: str) -> ImplementationDocument:
        run = _read_json_default(self.run_path(center_id, channel_id, monitor_id, run_id), default={})
        if not run:
            raise PublicTrustCenterPublicationMonitoringNotFoundError("Publication monitoring run not found.")
        return run

    def _assert_run_artifacts_current(self, run: ImplementationDocument, probe_results: ImplementationDocument, drift_report: ImplementationDocument, incident_report: ImplementationDocument, channel_state_snapshot: ImplementationDocument) -> None:
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

    def _file_index(self, export_dir: Path) -> ImplementationDocument:
        data = {"schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION, "source_hash": stable_hash([_file_record(export_dir, path) for path in _walk_files(export_dir)]), "files": [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "file-index.json"]}
        data["integrity_hash"] = monitoring_hash(data)
        return data











def monitoring_summary(run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    return {"run_id": run.get("run_id"), "monitor_id": run.get("monitor_id"), "publication_id": run.get("publication_id"), "status": run.get("status"), **summary}


def _default_requirements() -> dict[str, bool]:
    return {
        "require_ready": True,
        "require_anchor_current": True,
        "require_acceptance_board_signoff": True,
        "require_no_revoked": True,
        "require_current": True,
        "require_no_open_critical_incidents": True,
        "require_mirror": True,
        "require_external_channel_state": True,
    }


def _default_drift_policy() -> dict[str, str]:
    return {
        "missing_file": "critical",
        "hash_mismatch": "critical",
        "extra_file": "high",
        "html_unsafe": "critical",
        "revoked": "critical",
        "superseded": "critical",
        "state_missing": "critical",
        "state_stale": "critical",
        "redaction": "critical",
    }


def _drift(drift_type: str, severity: str, message: str, evidence: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"drift_id": "drift-" + stable_hash({"type": drift_type, "message": message, "evidence": evidence or {}})[:12], "drift_type": drift_type, "severity": severity, "message": message, "evidence": evidence or {}, "manual_action": {"status": "manual_required", "action_type": _manual_action_for_drift(drift_type)}}


def _manual_action_for_drift(drift_type: str) -> str:
    if drift_type in {"publication_revoked", "publication_superseded", "publication_missing_from_state"}:
        return "publish_replacement"
    if drift_type.startswith("mirror_"):
        return "refresh_or_recopy_mirror"
    return "investigate_publication_drift"


def _overall_severity(drifts: list[ImplementationDocument]) -> str:
    severities = [str(item.get("severity") or "") for item in drifts]
    if "critical" in severities:
        return "critical"
    if "high" in severities:
        return "high"
    if "warning" in severities:
        return "warning"
    return "none"


def _run_status(drift_report: ImplementationDocument, incident_report: ImplementationDocument) -> str:
    summary = incident_report.get("summary") if isinstance(incident_report.get("summary"), dict) else {}
    if drift_report.get("status") == "failed" or int(summary.get("critical_count") or 0) > 0:
        return "failed"
    if drift_report.get("status") == "warning" or int(summary.get("open_count") or 0) > 0:
        return "warning"
    return "passed"


def _publication_state_row(channel_state: ImplementationDocument, publication_id: str) -> ImplementationDocument:
    for row in channel_state.get("publications", []) if isinstance(channel_state.get("publications"), list) else []:
        if isinstance(row, dict) and str(row.get("publication_id") or "") == str(publication_id):
            return row
    return {}


def _check_status_map(report: ImplementationDocument) -> dict[str, str]:
    return {str(item.get("check_id") or ""): str(item.get("status") or "") for item in report.get("checks", []) if isinstance(item, dict)}


def _event(event_type: str, payload: ImplementationDocument, previous_event_hash: str | None, now: str, prefix: str, index: int) -> ImplementationDocument:
    payload = sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS)
    event = {
        "event_id": f"{prefix}-{index:06d}",
        "event_type": event_type,
        "created_at": now,
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "previous_event_hash": previous_event_hash,
    }
    event["event_hash"] = stable_hash(event)
    return event


def _incident_from_events(center_id: str, channel_id: str, monitor_id: str, incident_id: str, events: list[ImplementationDocument]) -> ImplementationDocument:
    if not events:
        return {}
    opened = next((event for event in events if event.get("event_type") == "opened"), events[0])
    payload = opened.get("payload") if isinstance(opened.get("payload"), dict) else {}
    status = "open"
    evidence = {
        "drift_report_hash": payload.get("drift_report_hash"),
        "probe_results_hash": payload.get("probe_results_hash"),
        "channel_state_latest_event_hash": payload.get("channel_state_latest_event_hash"),
    }
    latest_run_id = payload.get("run_id")
    for event in events:
        event_type = str(event.get("event_type") or "")
        epayload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if epayload.get("run_id"):
            latest_run_id = epayload.get("run_id")
        if event_type in {"opened", "reopened"}:
            status = "open"
        elif event_type == "acknowledged":
            status = "open"
        elif event_type == "resolved":
            status = "resolved"
        elif event_type == "waived":
            status = "waived"
    issue_type = str(payload.get("issue_type") or "monitoring_drift")
    severity = str(payload.get("severity") or "critical")
    return {
        "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
        "package_type": PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE,
        "incident_id": incident_id,
        "monitor_id": monitor_id,
        "center_id": center_id,
        "channel_id": channel_id,
        "first_run_id": payload.get("run_id"),
        "latest_run_id": latest_run_id,
        "publication_id": None,
        "status": status,
        "severity": severity,
        "issue_type": issue_type,
        "title": _incident_title(issue_type),
        "evidence": evidence,
        "manual_actions": [{"action_type": _manual_action_for_drift(issue_type), "status": "manual_required", "reason": _incident_title(issue_type)}],
    }


def _incident_title(issue_type: str) -> str:
    return {
        "publication_revoked": "Published snapshot has been revoked",
        "publication_superseded": "Published snapshot has been superseded",
        "mirror_file_missing": "Publication mirror is missing files",
        "mirror_file_hash_mismatch": "Publication mirror file hash mismatch",
        "mirror_extra_file": "Publication mirror contains unexpected files",
        "publication_zip_hash_mismatch": "Publication ZIP does not match channel state",
    }.get(issue_type, "Publication monitoring drift detected")


def _event_chain_valid(events: list[ImplementationDocument]) -> bool:
    previous: str | None = None
    for event in events:
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(event.get("payload") if isinstance(event.get("payload"), dict) else {}):
            return False
        expected = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("event_hash") != expected:
            return False
        previous = str(event.get("event_hash") or "")
    return True


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "item"


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _public_path_hint(value: Any) -> str | None:
    if not value:
        return None
    return Path(str(value)).name


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    tmp_path = path.with_name(f".tmp-{os.getpid()}-{threading.get_ident()}.json")
    try:
        with open(_fs_path(tmp_path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
        os.replace(_fs_path(tmp_path), _fs_path(path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not os.path.exists(_fs_path(path)):
        return dict(default or {})
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[ImplementationDocument]) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_sanitize(row), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _checksum_json(export_dir: Path) -> ImplementationDocument:
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "monitoring-manifest.json"}]
    data = {"schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = monitoring_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    text = "\n".join(
        [
            "MusicForge Public Trust Center Publication Monitoring",
            "",
            "This package contains a local publication monitoring run, drift report, incident summary, channel state snapshot, and verifier reports.",
            "Use verify-public-trust-center-publication-monitoring-package with --publication-channel-state for current revoke/supersede checks.",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(root):
                with open(_fs_path(resolved), "rb") as handle:
                    archive.writestr(entry, handle.read())
        os.replace(_fs_path(tmp_path), _fs_path(zip_path))
    finally:
        if os.path.exists(_fs_path(tmp_path)):
            os.unlink(_fs_path(tmp_path))


def _safe_copy(source: Path, target: Path, root: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    _ensure_within(root.resolve(), target)
    if not os.path.isfile(_fs_path(source)) or os.path.islink(_fs_path(source)):
        raise PublicTrustCenterPublicationMonitoringStateError(f"Required monitoring source file is missing: {source.name}")
    _mkdir(target.parent)
    shutil.copyfile(_fs_path(source), _fs_path(target))


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterPublicationMonitoringStateError("Resolved path escapes Public Trust Center publication monitoring root.")


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _sha256(path: Path) -> str | None:
    if not os.path.isfile(_fs_path(path)):
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS)


def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _from_fs_path(value: str) -> Path:
    if os.name != "nt":
        return Path(value)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value.removeprefix("\\\\?\\UNC\\"))
    if value.startswith("\\\\?\\"):
        return Path(value.removeprefix("\\\\?\\"))
    return Path(value)
