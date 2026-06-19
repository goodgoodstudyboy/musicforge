from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.trust_operations_hub import TrustOperationsHubStore, hub_hash


TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION = 1
TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_board"
TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_report"
TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_manifest"
TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}
TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}

INCIDENT_EXPORT_ENTRIES = {
    "README.txt",
    "incident-board.json",
    "incident-board-report.json",
    "incident-source-summary.json",
    "incidents.json",
    "incident-events.jsonl",
    "remediation-plans.json",
    "remediation-results.json",
    "evidence-index.json",
    "closeout-summary.json",
    "trust-operations-incident-manifest.json",
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


class TrustOperationsIncidentError(ValueError):
    pass


class TrustOperationsIncidentNotFoundError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStateError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-incidents",
        *,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.lock = threading.RLock()

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

    def refresh_board(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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
            board = {
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
            if board["summary"]["open_count"] == 0 and board["summary"]["stale_count"] == 0:
                board["status"] = "ready_for_closeout"
            board["integrity_hash"] = incident_hash(board)
            _write_json(self.board_path(hub_id), board)
            _write_json(self.source_snapshot_path(hub_id), source)
            self._append_board_event(hub_id, "incident_board_refreshed", {"board_hash": board["integrity_hash"], "created_count": created_count, "updated_count": updated_count}, now=now)
            return _sanitize({"incident_board": board, "created_count": created_count, "updated_count": updated_count, "stale_count": stale_count, "incidents": self.list_incidents(hub_id)})

    def read_board(self, hub_id: str) -> dict[str, Any]:
        if not self.board_path(hub_id).exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident Board not found.")
        return _read_json(self.board_path(hub_id))

    def list_incidents(self, hub_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
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

    def read_incident(self, hub_id: str, incident_id: str) -> dict[str, Any]:
        path = self.incident_path(hub_id, incident_id)
        if not path.exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident not found.")
        return _read_json(path)

    def triage_incident(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def create_plan(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            plan_id = _safe_id(str(payload.get("plan_id") or "rp-000001"))
            steps = payload.get("steps") if isinstance(payload.get("steps"), list) else _default_plan_steps(incident)
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

    def add_evidence(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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
            evidence_id = _safe_id(str(payload.get("evidence_id") or _next_id(self.evidence_dir(hub_id, incident_id), "ev")))
            evidence = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "evidence_id": evidence_id,
                "incident_id": incident_id,
                "kind": str(payload.get("kind") or "external_verification_report"),
                "component_type": component_type,
                "component_id": component_id,
                "status": report.get("status") or "missing",
                "payload_hash": stable_hash(report),
                "verification_report_hash": verification_hash(report),
                "zip_sha256": report.get("zip_sha256"),
                "zip_size_bytes": report.get("zip_size_bytes"),
                "manifest_hash": report.get("manifest_hash"),
                "source_hash": report.get("source_hash"),
                "created_at": now,
                "redaction_status": "passed",
                "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
            }
            evidence["integrity_hash"] = incident_hash(evidence)
            _write_json(self.evidence_path(hub_id, incident_id, evidence_id), evidence)
            self._write_evidence_index(hub_id, incident_id)
            if incident.get("status") in {"open", "triaged", "in_progress"}:
                incident["status"] = "waiting_verification"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_evidence_added", now=now)
            return _sanitize(evidence)

    def verify_fix(self, hub_id: str, incident_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            incident = self._mutable_incident(hub_id, incident_id)
            evidence_index = self._read_evidence_index(hub_id, incident_id)
            current = self._incident_source_current(hub_id, incident)
            passed_evidence = [
                item
                for item in evidence_index.get("evidence", [])
                if isinstance(item, dict)
                and item.get("status") == "passed"
                and item.get("component_id") == incident.get("detected_from", {}).get("component_id")
            ]
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

    def close_incident(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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
                {"check_id": "required_external_verification_present", "status": "passed" if _evidence_summary(evidence_index)["passed_count"] else "failed", "severity": "blocking"},
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

    def archive_incident(self, hub_id: str, incident_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def export_board(self, hub_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def build_zip(self, hub_id: str, *, now: str | None = None) -> dict[str, Any]:
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

    def verify_zip(self, hub_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.trust_operations_hub_incident_verifier import verify_trust_operations_hub_incident_package

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

    def _source_summary(self, hub_id: str, report_id: str, docs: dict[str, dict[str, Any]]) -> dict[str, Any]:
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

    def _incident_candidates(self, hub_id: str, report_id: str, source: dict[str, Any], docs: dict[str, dict[str, Any]], now: str) -> list[dict[str, Any]]:
        del now
        rows: list[dict[str, Any]] = []
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

    def _write_incident(self, hub_id: str, incident: dict[str, Any], *, event_type: str, now: str) -> None:
        incident["integrity_hash"] = incident_hash(incident)
        _write_json(self.incident_path(hub_id, str(incident["incident_id"])), incident)
        self._append_incident_event(hub_id, str(incident["incident_id"]), event_type, {"status": incident.get("status"), "incident_hash": incident["integrity_hash"]}, now=now)

    def _append_incident_event(self, hub_id: str, incident_id: str, event_type: str, payload: dict[str, Any], *, now: str) -> None:
        rows = _read_jsonl(self.incident_events_path(hub_id, incident_id))
        event = {"incident_id": incident_id, "event_id": f"{incident_id}-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.incident_events_path(hub_id, incident_id), event)

    def _append_board_event(self, hub_id: str, event_type: str, payload: dict[str, Any], *, now: str) -> None:
        rows = _read_jsonl(self.board_events_path(hub_id))
        event = {"event_id": f"tohi-board-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.board_events_path(hub_id), event)

    def _mutable_incident(self, hub_id: str, incident_id: str) -> dict[str, Any]:
        incident = self.read_incident(hub_id, incident_id)
        if incident.get("status") in {"closed", "archived"}:
            raise TrustOperationsIncidentStateError("Closed or archived incidents are read-only.")
        if incident.get("integrity_hash") != incident_hash(incident):
            raise TrustOperationsIncidentStateError("Trust Operations Incident integrity failed.")
        return incident

    def _read_evidence_index(self, hub_id: str, incident_id: str) -> dict[str, Any]:
        return _read_json_default(self.evidence_index_path(hub_id, incident_id), default={"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": [], "summary": _evidence_summary({"evidence": []})})

    def _write_evidence_index(self, hub_id: str, incident_id: str) -> dict[str, Any]:
        rows = []
        for path in sorted(self.evidence_dir(hub_id, incident_id).glob("ev-*.json")):
            rows.append(_read_json(path))
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        _write_json(self.evidence_index_path(hub_id, incident_id), index)
        return index

    def _incident_source_current(self, hub_id: str, incident: dict[str, Any]) -> bool:
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

    def _current_source_for_closeout(self, hub_id: str, incident: dict[str, Any]) -> dict[str, Any]:
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

    def _export_events(self, hub_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for incident in self.list_incidents(hub_id, include_archived=True):
            rows.extend(_read_jsonl(self.incident_events_path(hub_id, str(incident.get("incident_id") or ""))))
        return sorted(rows, key=lambda item: str(item.get("event_id") or ""))

    def _all_docs(self, hub_id: str, filename: str) -> list[dict[str, Any]]:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob(f"*/{filename}")):
            rows.append(_read_json(path))
        return rows

    def _aggregate_evidence(self, hub_id: str) -> dict[str, Any]:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/evidence/evidence-index.json")):
            index = _read_json(path)
            rows.extend([item for item in index.get("evidence", []) if isinstance(item, dict)])
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        return index

    def _closeout_summary(self, hub_id: str) -> dict[str, Any]:
        closeouts = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/closeout-report.json")):
            closeouts.append(_read_json(path))
        data = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "closeouts": closeouts, "summary": {"closeout_count": len(closeouts), "passed_count": sum(1 for row in closeouts if row.get("status") == "passed"), "failed_count": sum(1 for row in closeouts if row.get("status") == "failed")}}
        data["integrity_hash"] = incident_hash(data)
        return data

    def _board_report(self, board: dict[str, Any], incidents: list[dict[str, Any]], source: dict[str, Any], events: list[dict[str, Any]], evidence_index: dict[str, Any], closeout_summary: dict[str, Any], now: str) -> dict[str, Any]:
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


def incident_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS})


def incident_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def _default_plan_steps(incident: dict[str, Any]) -> list[dict[str, Any]]:
    component_type = str(incident.get("detected_from", {}).get("component_type") or "")
    action = {
        "release_verification": "verify_release_package",
        "distribution_verification": "verify_distribution_package",
        "submission_verification": "verify_submission_package",
        "submission_evidence_verification": "verify_submission_evidence_package",
        "release_operations_verification": "verify_release_operations_package",
    }.get(component_type, "manual_required")
    return [
        {"action_type": "manual_required", "title": "Review and repair the underlying Trust Operations blocker."},
        {"action_type": action, "title": f"Verify {component_type or 'component'} evidence."},
    ]


def _board_summary(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    open_rows = [item for item in incidents if item.get("status") in BLOCKING_STATUSES]
    blocking_open = [item for item in open_rows if item.get("blocking")]
    critical = [item for item in open_rows if item.get("severity") == "critical"]
    high = [item for item in open_rows if item.get("severity") == "high"]
    stale = [item for item in incidents if item.get("stale")]
    return {
        "total_incidents": len(incidents),
        "open_count": len(open_rows),
        "closed_count": sum(1 for item in incidents if item.get("status") == "closed"),
        "critical_count": len(critical),
        "high_count": len(high),
        "blocking_open_count": len(blocking_open),
        "stale_count": len(stale),
        "ready_for_hub_signoff": len(open_rows) == 0 and len(stale) == 0,
    }


def _evidence_summary(index: dict[str, Any]) -> dict[str, int]:
    rows = index.get("evidence") if isinstance(index.get("evidence"), list) else []
    return {
        "evidence_count": len(rows),
        "passed_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "passed"),
        "failed_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "failed"),
    }


def _category(requirement: str, source_type: str) -> str:
    if source_type.endswith("delivery"):
        if requirement.endswith("_verified"):
            return "delivery_verification_missing"
        return "delivery_blocker"
    if "monitoring" in requirement:
        return "publication_monitoring_incident"
    return "hub_blocker"


def _component_type_from_component_id(component_id: str) -> str:
    prefix = str(component_id).split(":", 1)[0]
    return {
        "release": "release_verification",
        "distribution": "distribution_verification",
        "submission": "submission_verification",
        "submission-evidence": "submission_evidence_verification",
        "release-operations": "release_operations_verification",
        "publication-monitoring": "publication_monitoring_verification",
    }.get(prefix, prefix)


def _component_type_from_check_id(check_id: str) -> str:
    for marker, component_type in (
        ("release_verification", "release_verification"),
        ("distribution_verification", "distribution_verification"),
        ("submission_evidence_verification", "submission_evidence_verification"),
        ("submission_verification", "submission_verification"),
        ("release_operations_verification", "release_operations_verification"),
        ("monitoring", "publication_monitoring_verification"),
    ):
        if marker in check_id:
            return component_type
    return "trust_operations_hub"


def _component_id_from_check_id(component_type: str, check_id: str) -> str:
    prefix = {
        "release_verification": "release",
        "distribution_verification": "distribution",
        "submission_verification": "submission",
        "submission_evidence_verification": "submission-evidence",
        "release_operations_verification": "release-operations",
        "publication_monitoring_verification": "publication-monitoring",
    }.get(component_type, "hub")
    if check_id.endswith("_component_coverage"):
        return f"{prefix}:coverage"
    match = re.search(r"_(release|distribution|submission|submission_evidence|release_operations)_([A-Za-z0-9_]+)_hash$", check_id)
    if match:
        return f"{prefix}:{match.group(2).replace('_', '-')}"
    return f"{prefix}:verification"


def _contains_sensitive_value(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    markers = (
        "sk-",
        "bearer ",
        "github" + "_pat_",
        "x-access" + "-token",
        "github" + "key",
        "c:" + "\\users\\",
        "\\\\",
    )
    return any(marker in lowered for marker in markers)


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text(
        "MusicForge Trust Operations Incident Board\n\nThis package contains local incident response and remediation closeout evidence for Trust Operations Hub blockers.\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return read_json(path)


def _read_json_default(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


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


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.tmp")
    _mkdir(zip_path.parent)
    if tmp_path.exists():
        tmp_path.unlink()
    with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)
    tmp_path.replace(zip_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value


def _from_fs_path(value: str) -> Path:
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if os.name == "nt" and value.startswith("\\\\?\\"):
        return Path(value[4:])
    return Path(value)


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
